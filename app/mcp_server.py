"""第6回: 用語集と各回の要点を MCP サーバーとして公開する。

使い方:
    uv run python -m app.mcp_agent --list-tools     # このサーバーが公開するツールを一覧する（APIキー不要）
    uv run python -m app.mcp_server --http          # Streamable HTTP で起動する（http://127.0.0.1:8000/mcp）

引数なしで実行すると stdio（標準入出力）で待ち受ける。これは MCP クライアント（app.mcp_agent など）が
サブプロセスとして起動する使い方なので、手で実行すると入力待ちのまま止まって見える。

第3回では tools.py の関数を agent.py に直接登録した。MCP サーバーにすると、同じ関数を
エージェントのプログラム（app/mcp_agent.py）からも、MCP に対応したほかのソフトウェアからも、
共通の手順で使えるようになる。
"""

import argparse
import json

from mcp.server.mcpserver import MCPServer

from app import tools

# サーバーの名前と説明。クライアントに表示される（設定ファイル側のキー "glossary" とは別物）
server = MCPServer(
    "aie2026-glossary",
    instructions="AIE2026（AIエンジニアリング実践講座）の用語集と各回の要点を提供する。",
)

# 第3回と同じ関数を、そのまま MCP のツールとして公開する。docstring と型ヒントが説明文になる
server.tool()(tools.search_glossary)

# TODO(宿題・基礎): get_lecture_summary も公開しよう
server.tool()(tools.get_lecture_summary)

MAX_QUIZ_QUESTIONS = 5


# 宿題・実装: 用語集からクイズの材料を作るツール。関数に @server.tool() を付けると MCP のツールになる
@server.tool()
def make_quiz(lecture: int, num_questions: int = 3) -> str:
    """指定した回（1始まりの整数）の用語集から、クイズの問題と模範解答を作って返す。

    「第2回のクイズを作って」のように、回を指定してクイズや確認問題を頼まれたときに使う。
    num_questions は問題数（1〜5、省略すると3）。
    """
    by_lecture: dict[int, list[dict]] = {}
    for entry in tools.load_glossary():
        by_lecture.setdefault(entry["lecture"], []).append(entry)

    # 範囲外の引数は例外にせず、モデルが次にどうすればよいか分かるメッセージを return で返す
    if lecture not in by_lecture:
        available = ", ".join(str(n) for n in sorted(by_lecture))
        return (
            f"第{lecture}回のクイズは作れません。用語集に第{lecture}回の用語がないためです。"
            f"クイズを作れる回: {available}。lecture にはこのどれかを指定してください。"
        )
    if not 1 <= num_questions <= MAX_QUIZ_QUESTIONS:
        return (
            f"問題数 {num_questions} は範囲外です。"
            f"num_questions には 1 から {MAX_QUIZ_QUESTIONS} までの整数を指定してください。"
        )

    entries = by_lecture[lecture][:num_questions]
    return json.dumps(
        {
            "lecture": lecture,
            "questions": [
                {"question": f"「{e['term']}」とは何か、説明してください。", "answer": e["definition"]}
                for e in entries
            ],
        },
        ensure_ascii=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="用語集 MCP サーバー")
    parser.add_argument("--http", action="store_true", help="Streamable HTTP で起動する（既定は stdio）")
    args = parser.parse_args()
    if args.http:
        print("MCP サーバーを http://127.0.0.1:8000/mcp で起動します（Ctrl+C で停止）")
        server.run(transport="streamable-http")
    else:
        # stdio では標準出力がプロトコルの通信路になるので、print してはいけない
        server.run()


if __name__ == "__main__":
    main()
