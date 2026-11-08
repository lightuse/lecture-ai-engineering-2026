"""宿題（発展 a）: 演習のエージェントを Google ADK で組み立て直したもの。

指示（INSTRUCTIONS）とツール関数は app/ のものをそのまま使い、組み立てる部分だけを ADK で書く。
動かす（リポジトリの直下で）:
    PYTHONPATH=. uv run --with google-adk adk run adk_agent/glossary_agent
"""

from google.adk.agents import Agent

from app import tools
from app.agent import INSTRUCTIONS
from app.config import MODEL

root_agent = Agent(
    model=MODEL,  # 既定は gemini-3.5-flash-lite（演習と同じ。AIE_MODEL で切り替え）
    name="glossary_agent",
    description="AIE2026 の用語集と講義の要点を使って答える学習支援エージェント",
    instruction=INSTRUCTIONS,
    # 関数をそのまま渡すと、ADK が docstring と型ヒントからツールの説明を作る（Pydantic AI と同じ）
    tools=[tools.search_glossary, tools.get_lecture_summary],
)
