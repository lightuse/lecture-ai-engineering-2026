"""実SQLiteと固定ベクトルで、索引作成から検索までを確認する。APIは呼ばない。"""

import json
from unittest.mock import Mock

import pytest

from app import retrieval
from scripts.build_rag_index import build_index


@pytest.fixture
def materials(tmp_path):
    source = tmp_path / "lectures.json"
    source.write_text(json.dumps([
        {"id": f"lec{n:02d}-main", "title": f"講義{n}", "content": [
            {"section": "章", "content": [
                {"id": f"lec{n:02d}-main-p001", "title": f"ページ{n}",
                 "page": 1, "content": f"本文{n}"}]}]}
        for n in (1, 2, 5)
    ], ensure_ascii=False), encoding="utf-8")
    return source, tmp_path / "index.sqlite3"


def test_built_index_can_be_searched(materials, monkeypatch):
    source, database = materials
    texts = []

    def embed(text, task):
        assert task == "RETRIEVAL_DOCUMENT"
        texts.append(text)
        return [1, 0] if "本文1" in text else [0, 1]

    result = build_index(source, database, embedder=embed)
    assert result["pages"] == 2  # 第5回の資料は検索対象に含めない
    assert all("章" in text and "ページ" in text for text in texts)
    monkeypatch.setattr(retrieval, "RAG_DB", database)
    monkeypatch.setattr(retrieval, "embed_text", lambda *_: [1, 0])
    hits = retrieval.search("質問")
    assert [h["page_id"] for h in hits] == ["lec01-main-p001", "lec02-main-p001"]
    assert hits[0]["content"] == "本文1"
    assert hits[0]["distance"] == pytest.approx(0)


def test_existing_index_survives_failed_rebuild(materials):
    source, database = materials
    build_index(source, database, embedder=lambda *_: [1, 0])
    before = database.read_bytes()
    embed = Mock(side_effect=RuntimeError("埋め込みに失敗"))
    with pytest.raises(FileExistsError):
        build_index(source, database, embedder=embed)
    embed.assert_not_called()
    with pytest.raises(RuntimeError, match="埋め込みに失敗"):
        build_index(source, database, rebuild=True, embedder=embed)
    assert database.read_bytes() == before
    assert not list(database.parent.glob(".rag-build-*"))


def _page(document_id, number):
    return {"page_id": f"{document_id}-p{number:03d}", "document_id": document_id,
            "page": number, "title": f"p{number}", "content": f"本文{number}"}


def test_add_neighbor_pages_keeps_document_boundary_and_no_duplicates():
    """前後ページは同じ資料の中だけで付け、同じページを重複して返さない。"""
    pages = [_page("lec01-main", n) for n in (1, 2, 3)] + [_page("lec02-main", n) for n in (1, 2, 3, 4)]
    # lec02のp.1（資料の先頭）、p.2（p.1の隣で、それ自体も検索結果）、p.4 が見つかった場合
    hits = [{**_page("lec02-main", n), "distance": d} for n, d in ((1, 0.1), (2, 0.2), (4, 0.3))]

    results = retrieval.add_neighbor_pages(hits, pages, width=1)

    ids = [r["page_id"] for r in results]
    assert ids == ["lec02-main-p001", "lec02-main-p002", "lec02-main-p003", "lec02-main-p004"]
    assert len(ids) == len(set(ids))
    assert all(r["document_id"] == "lec02-main" for r in results)  # lec01の末尾へまたがない
    assert [r["role"] for r in results] == ["hit", "hit", "neighbor", "hit"]
    neighbor = results[2]
    assert neighbor["neighbor_of"] == "lec02-main-p002" and "distance" not in neighbor
    assert neighbor["content"] == "本文3"


def test_search_with_neighbors_is_plain_search_by_default(monkeypatch):
    """RAG_NEIGHBOR_PAGESが0なら、通常の検索結果をそのまま返す。"""
    hits = [{**_page("lec02-main", 2), "distance": 0.1}]
    monkeypatch.setattr(retrieval, "search", lambda query: hits)
    monkeypatch.setattr(retrieval, "RAG_NEIGHBOR_PAGES", 0)
    assert retrieval.search_with_neighbors("質問") == hits


def test_match_terms_uses_word_boundary_and_longest_match():
    """英数字の別名は単語境界で一致させ、重なる用語は長く一致した方だけを残す。"""
    terms = [{"id": "t-pi", "title": "Pi", "aliases": ["Pi"]},
             {"id": "t-tool", "title": "ツール", "aliases": ["ツール"]},
             {"id": "t-ext", "title": "外部ツール", "aliases": ["外部ツール"]},
             {"id": "t-mcp", "title": "MCP（Model Context Protocol）", "aliases": ["MCP"]}]
    found = retrieval.match_terms("pipで入れたmcpと外部ツールの関係は？", terms)
    assert [(t["id"], t["matched"]) for t in found] == [("t-ext", "外部ツール"), ("t-mcp", "MCP")]


def test_spread_by_section_takes_each_section_before_second_page():
    """距離が近い章に偏らせず、各章から1ページずつ先に選ぶ。"""
    def candidate(lecture, section, number, distance):
        return {"page_id": f"lec{lecture:02d}-main-p{number:03d}", "lecture": lecture,
                "section": section, "distance": distance}
    candidates = [candidate(3, "A", 1, 0.1), candidate(3, "A", 2, 0.2), candidate(3, "A", 3, 0.3),
                  candidate(1, "B", 1, 0.5), candidate(2, "C", 1, 0.6)]
    picked = retrieval.spread_by_section(candidates, limit=4)
    assert [(p["lecture"], p["distance"]) for p in picked] == [(3, 0.1), (1, 0.5), (2, 0.6), (3, 0.2)]
