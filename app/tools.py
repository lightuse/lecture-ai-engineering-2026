"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import re
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"  # .gitignore 済み
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def _safe_filename(title: str) -> str:
    """ファイル名に使えない文字を "_" に置き換え、長すぎる名前を切り詰める。"""
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("._")
    return name[:50] or "untitled"


def save_learning_log(title: str, content: str) -> str:
    """学習の記録を Markdown ファイルとして learning_log/ フォルダに保存し、保存先を返す。

    利用者が「記録して」「メモを残して」「学習ログに保存して」のように、
    学んだことを残すよう頼んだときだけ使う。頼まれていないときは使わない。
    title には記録の短い題名（例: "LoRAとQLoRAの違い"）、
    content には保存する本文（Markdown）を入れる。
    実行の前に利用者の確認がある。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = LOG_DIR / f"{stamp}_{_safe_filename(title)}.md"
    n = 2
    while path.exists():  # 同じ秒に同じ題名で保存しても上書きしない
        path = LOG_DIR / f"{stamp}_{_safe_filename(title)}_{n}.md"
        n += 1
    body = content.strip()
    if not body.startswith("# "):  # モデルが本文に見出しを入れてきたら、二重にしない
        body = f"# {title}\n\n{body}"
    path.write_text(body + "\n", encoding="utf-8")
    return f"保存しました: {path.relative_to(LOG_DIR.parent)}"
