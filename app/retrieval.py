"""第5回: ページ単位のベクトル検索。"""

import argparse
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from collections import defaultdict, deque
from pathlib import Path

from google import genai
from google.genai import types
from pydantic_ai.exceptions import ModelHTTPError
import sqlite_vec

from app.config import (
    EMBEDDING_DIMENSIONS, EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL,
    RAG_DB, RAG_DOCUMENT_IDS, RAG_NEIGHBOR_PAGES, RAG_SOURCE, RAG_TOP_K, RAG_TREE, get_api_key,
    RAG_GRAPH, GRAPH_START_K, GRAPH_HOPS, GRAPH_MAX_RESULTS, TERM_MAP_MAX_RESULTS,
)


def get_all_materials() -> str:
    """全資料を、講義・章・ページの情報付きで1つの文字列にまとめる。"""
    documents = json.loads(RAG_SOURCE.read_text(encoding="utf-8"))
    return "\n\n".join(
        f"資料: {document['id']} / {document['title']}\n"
        f"章: {section['section']}\n"
        f"ページ: PDF p.{page['page']} / {page['title']}\n{page['content']}"
        for document in documents
        for section in document["content"]
        for page in section["content"]
    )

def load_pages(source: Path = RAG_SOURCE) -> list[dict]:
    """資料→章→ページのJSONを、対象資料のページ一覧に変換する。"""
    documents = json.loads(source.read_text(encoding="utf-8"))
    pages = []
    for document in documents:
        if document["id"] not in RAG_DOCUMENT_IDS:
            continue
        for section in document["content"]:
            for page in section["content"]:
                pages.append({"page_id": page["id"], "document_id": document["id"],
                              "lecture": int(document["id"][3:5]), "document_title": document["title"],
                              "section": section["section"], "title": page["title"],
                              "page": page["page"], "content": page["content"]})
    return pages


def browse_tree(node_id: str | None = None) -> dict:
    """直下のページは先頭文、指定したページ自身は全文を返す。"""
    tree = json.loads(RAG_TREE.read_text(encoding="utf-8"))
    tree["children"] = [node for node in tree["children"] if node["id"] in RAG_DOCUMENT_IDS]
    node_id = node_id or tree["id"]
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}

    def describe(node, full=False):
        info = {key: node[key] for key in ("id", "kind", "title")}
        if node["kind"] == "page":
            info.update({key: value for key, value in pages[node["id"]].items() if key != "page_id"})
            if not full:
                info["content"] = re.split(r"(?<=[。！？])|\n", info["content"].strip(), maxsplit=1)[0]
        return info

    remaining = [tree]
    while remaining:
        node = remaining.pop()
        if node["id"] == node_id:
            return {
                "node": describe(node, full=True),
                "children": [describe(child) for child in node.get("children", [])],
            }
        remaining.extend(node.get("children", []))
    raise ValueError("対象の目次ノードが見つかりません。")


def read_page(page_id: str) -> dict:
    """第1〜3回の本講義から、指定した1ページの本文と引用情報を返す。"""
    for page in load_pages(RAG_SOURCE):
        if page["page_id"] == page_id:
            return page
    raise ValueError("対象のページが見つかりません。")


def normalized_vector(values: list[float]) -> list[float]:
    """ベクトルの長さを1に揃える。"""
    norm = math.hypot(*values)
    if norm == 0:
        raise ValueError("埋め込みがゼロベクトルです。")
    return [value / norm for value in values]


def embed_text(text: str, task_type: str) -> list[float]:
    """Geminiで文章を埋め込む。入力上限を超えた場合は切り捨てず停止する。"""
    with genai.Client(api_key=get_api_key()) as client:
        count = client.models.count_tokens(model=EMBEDDING_MODEL, contents=text).total_tokens
        if count is None or count > EMBEDDING_MAX_TOKENS:
            raise ValueError(f"埋め込み入力が上限を超えるか計測不能です: {count} tokens。")
        response = client.models.embed_content(
            model=EMBEDDING_MODEL, contents=text,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
        )
    embedding = response.embeddings[0]
    if embedding.statistics and embedding.statistics.truncated:
        raise ValueError("埋め込みAPIが本文を切り捨てました。")
    return normalized_vector(embedding.values)


@contextmanager
def open_index(path: Path):
    """既存の検索DBを読み取り専用で開き、終了時に閉じる。"""
    if not path.is_file():
        raise FileNotFoundError("検索DBがありません。")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        yield db
    finally:
        db.close()


def search(query: str) -> list[dict]:
    """質問を埋め込み、近いページを最大RAG_TOP_K件返す。"""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("検索語が空です。")
    with open_index(RAG_DB) as db:
        vector = embed_text(query.strip(), "RETRIEVAL_QUERY")
        rows = db.execute("""
            SELECT page_id, document_id, lecture, document_title, section, title, page, content,
                   vec_distance_cosine(embedding, ?) AS distance
            FROM chunks ORDER BY distance, page_id LIMIT ?
        """, (sqlite_vec.serialize_float32(vector), RAG_TOP_K))
        return [dict(row) for row in rows]


def add_neighbor_pages(hits: list[dict], pages: list[dict], width: int = 1) -> list[dict]:
    """検索結果の各ページに、同じ資料の前後widthページを付けて返す。

    - 前後は同じdocument_idの中だけで探す（資料の先頭・末尾から別の資料へはまたがない）。
    - 同じページは1回だけ返す。検索で見つかったページは、他のページの前後としては重ねない。
    - 検索の順位ごとに「前のページ → 見つかったページ → 次のページ」の順に並べる。
    - roleは"hit"（検索で見つかった）か"neighbor"（前後として追加した）。
      neighborにはdistanceがなく、どのページの前後かをneighbor_ofに入れる。
    """
    hits = [{**hit, "role": "hit"} for hit in hits]
    if width <= 0:
        return hits
    by_document = defaultdict(list)
    for page in pages:
        by_document[page["document_id"]].append(page)
    position = {}
    for document_pages in by_document.values():
        document_pages.sort(key=lambda page: page["page"])
        for index, page in enumerate(document_pages):
            position[page["page_id"]] = index

    seen = {hit["page_id"] for hit in hits}
    results = []
    for hit in hits:
        before, after = [], []
        if hit["page_id"] in position:
            document_pages = by_document[hit["document_id"]]
            index = position[hit["page_id"]]
            for neighbor in document_pages[max(0, index - width):index + width + 1]:
                if neighbor["page_id"] in seen:
                    continue
                seen.add(neighbor["page_id"])
                item = {**neighbor, "role": "neighbor", "neighbor_of": hit["page_id"]}
                (before if neighbor["page"] < hit["page"] else after).append(item)
        results.extend(before + [hit] + after)
    return results


def search_with_neighbors(query: str) -> list[dict]:
    """通常の検索を行い、RAG_NEIGHBOR_PAGESが1以上なら前後のページも付ける。0なら通常の検索と同じ。"""
    hits = search(query)
    if RAG_NEIGHBOR_PAGES <= 0:
        return hits
    return add_neighbor_pages(hits, load_pages(RAG_SOURCE), RAG_NEIGHBOR_PAGES)


def match_terms(query: str, terms: list[dict]) -> list[dict]:
    """質問文に名前か別名が出てくる用語ノードを返す（埋め込みは使わない文字列一致）。

    - 英数字の別名は単語の境界で一致させる（"Pi"が"pip"に当たらないようにする）。
    - 「外部ツール」と「ツール」のように重なる場合は、長く一致した用語だけを残す。
    """
    text = query.casefold()
    found = []
    for term in terms:
        for alias in {term["title"], *term.get("aliases", [])}:
            name = alias.casefold()
            pattern = re.escape(name)
            if re.fullmatch(r"[a-z0-9 ._\-]+", name):
                pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
            for match in re.finditer(pattern, text):
                found.append((match.start(), match.end(), term["id"], alias))
    kept = {}
    for start, end, term_id, alias in found:
        covered = any(s <= start and end <= e and (e - s) > (end - start) for s, e, *_ in found)
        if not covered and (term_id not in kept or len(alias) > len(kept[term_id])):
            kept[term_id] = alias
    by_id = {term["id"]: term for term in terms}
    return [{"id": term_id, "title": by_id[term_id]["title"], "matched": alias}
            for term_id, alias in sorted(kept.items())]


def spread_by_section(candidates: list[dict], limit: int) -> list[dict]:
    """候補ページを「回・章」ごとに分け、各章の距離が近い順に1ページずつ交互に選ぶ。

    距離の近い順だけで選ぶと1つの章に偏るので、用語が出てくる章を先に広く拾う。
    """
    groups = defaultdict(list)
    for page in sorted(candidates, key=lambda page: (page["distance"], page["page_id"])):
        groups[(page["lecture"], page["section"])].append(page)
    queues = sorted(groups.values(), key=lambda pages: (pages[0]["distance"], pages[0]["page_id"]))
    selected = []
    while len(selected) < limit and any(queues):
        for pages in queues:
            if pages and len(selected) < limit:
                selected.append(pages.pop(0))
    return selected


def page_distances(query: str) -> dict[str, float]:
    """質問を1回だけ埋め込み、検索DBの全ページとの距離を返す。"""
    with open_index(RAG_DB) as db:
        vector = embed_text(query.strip(), "RETRIEVAL_QUERY")
        rows = db.execute("SELECT page_id, vec_distance_cosine(embedding, ?) AS distance FROM chunks",
                          (sqlite_vec.serialize_float32(vector),))
        return {row["page_id"]: row["distance"] for row in rows}


def search_term_map(query: str) -> dict:
    """用語ノードを入口に、その用語に触れているページを回・章にまたがって返す。

    1. 質問文と用語の名前・別名を照合し、Graphの用語ノードを入口にする。
    2. mentionsの関係を1 hopたどり、用語に触れているページをすべて候補にする。
    3. coverageに、候補ページを回・章ごとにまとめた一覧（本文なし）を入れる。
    4. resultsには、章ごとに交互に選んだ最大TERM_MAP_MAX_RESULTSページの本文を入れる。
    用語が見つからない質問では、通常の検索結果を返す。
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("検索語が空です。")
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}
    graph = json.loads(RAG_GRAPH.read_text(encoding="utf-8"))
    terms = match_terms(query, [node for node in graph["nodes"] if node["kind"] == "term"])
    term_ids = {term["id"] for term in terms}
    mentioned = defaultdict(set)
    for edge in graph["edges"]:
        if edge["relation"] != "mentions":
            continue
        for page_id, term_id in ((edge["source"], edge["target"]), (edge["target"], edge["source"])):
            if page_id in pages and term_id in term_ids:
                mentioned[page_id].add(term_id)
    if not mentioned:
        return {"terms": [], "coverage": [], "results": search(query),
                "note": "質問に用語集の用語が見つからないため、通常の検索結果を返した。"}

    distances = page_distances(query)
    titles = {term["id"]: term["title"] for term in terms}
    candidates = [{**pages[page_id], "distance": distances[page_id],
                   "terms": sorted(titles[t] for t in term_ids_of_page)}
                  for page_id, term_ids_of_page in mentioned.items() if page_id in distances]
    results = spread_by_section(candidates, TERM_MAP_MAX_RESULTS)
    returned = {page["page_id"] for page in results}
    sections = defaultdict(list)
    for page in sorted(candidates, key=lambda page: (page["lecture"], page["page"])):
        sections[(page["lecture"], page["section"])].append(page)
    coverage = [{"lecture": lecture, "section": section,
                 "pages": [{"page_id": page["page_id"], "page": page["page"], "title": page["title"],
                            "returned": page["page_id"] in returned} for page in members]}
                for (lecture, section), members in sections.items()]
    return {"terms": terms, "coverage": coverage, "results": results}


def search_graph(query: str) -> dict:
    """ベクトル検索を入口に、前後ページと共通用語で候補を広げる。"""
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}
    graph = json.loads(RAG_GRAPH.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph["nodes"]
             if node["kind"] == "term" or node["id"] in pages}
    adjacent = defaultdict(set)
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if edge["relation"] in ("next_page", "mentions") and a in nodes and b in nodes:
            adjacent[a].add(b)
            adjacent[b].add(a)

    seeds = [hit for hit in search(query) if hit["page_id"] in pages][:min(GRAPH_START_K, GRAPH_MAX_RESULTS)]
    seed_ids = {seed["page_id"] for seed in seeds}
    results, candidates = [], {}
    for rank, seed in enumerate(seeds):
        root = seed["page_id"]
        results.append({**pages[root], "distance": seed["distance"], "hops": 0,
                        "path": [{"id": root, "title": pages[root]["title"]}]})
        queue = deque([(root, [root])])
        visited = {root}
        while queue:
            current, path = queue.popleft()
            if len(path) - 1 >= GRAPH_HOPS:
                continue
            # 同じ深さなら、接続先が少ない用語からたどる。
            neighbors = sorted(adjacent[current], key=lambda n: (len(adjacent[n]), n))
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                route = path + [neighbor]
                queue.append((neighbor, route))
                if neighbor not in pages or neighbor in seed_ids:
                    continue
                frequency = max((len(adjacent[n]) for n in route if nodes[n]["kind"] == "term"), default=0)
                priority = (len(route) - 1, frequency, rank, neighbor)
                candidate = {**pages[neighbor], "hops": len(route) - 1,
                             "path": [{"id": n, "title": nodes[n]["title"]} for n in route]}
                if neighbor not in candidates or priority < candidates[neighbor][0]:
                    candidates[neighbor] = (priority, candidate)
    expanded = [candidate for _, candidate in sorted(candidates.values())]
    return {"seeds": results, "expanded": expanded[:max(0, GRAPH_MAX_RESULTS - len(results))],
            "max_hops": GRAPH_HOPS}



def run_full_context(agent, question: str, model, instructions: str, prompt_template: str):
    """全資料を一括投入し、検索ツールを使わずに回答する。"""
    prompt = prompt_template.format(materials=get_all_materials(), question=question)
    print(f"[full-context] 入力{len(prompt):,}文字")
    try:
        with agent.override(tools=[], instructions=instructions):
            return agent.run_sync(prompt, model=model)
    except ModelHTTPError as e:
        print(f"[full-context] APIエラー HTTP {e.status_code}: {e.body}")
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="エージェントを使わず、講義資料の検索だけを実行する")
    parser.add_argument("query", help="調べたい内容")
    args = parser.parse_args()
    for i, result in enumerate(search_with_neighbors(args.query), 1):
        print(f"\n{'=' * 60}\n検索結果 {i}\n{'=' * 60}")
        if result.get("role") == "neighbor":
            print(f"（{result['neighbor_of']} の前後として追加）")
        print(f"講義: {result['document_title']}")
        print(f"章: {result['section']}")
        print(f"タイトル: {result['title']}")
        print(f"ページ: {result['page']}")
        print(f"\n{result['content']}")
