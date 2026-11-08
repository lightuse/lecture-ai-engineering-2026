"""宿題（実装）: save_learning_log と、保存前の承認（requires_approval=True）のテスト。

TestModel を使うので、APIキーも利用枠も使わない。保存先は tmp_path に差し替える。
"""

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, run_with_approval


@pytest.fixture(autouse=True)
def log_dir(tmp_path, monkeypatch):
    path = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LOG_DIR", path)
    return path


def _returns(result, name):
    return [
        p for m in result.all_messages() for p in m.parts
        if isinstance(p, ToolReturnPart) and p.tool_name == name
    ]


def test_save_learning_log_writes_markdown(log_dir):
    message = tools.save_learning_log("LoRA/QLoRA の違い", "- QLoRA は量子化する")
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    assert "/" not in files[0].name.split("_", 1)[1]  # 題名の「/」はファイル名に入らない
    assert files[0].read_text(encoding="utf-8") == "# LoRA/QLoRA の違い\n\n- QLoRA は量子化する\n"
    assert message.startswith("保存しました: learning_log/")


def test_heading_is_not_duplicated(log_dir):
    tools.save_learning_log("RAG", "# RAG\n\n本文")
    text = next(log_dir.glob("*.md")).read_text(encoding="utf-8")
    assert text.count("# RAG") == 1


def test_save_learning_log_does_not_overwrite(log_dir):
    tools.save_learning_log("同じ題名", "1回目")
    tools.save_learning_log("同じ題名", "2回目")
    assert len(list(log_dir.glob("*.md"))) == 2


def test_tool_is_registered_with_approval():
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = agent.run_sync("今日の学びを記録して")
    # 承認待ちで止まり、DeferredToolRequests が返る（まだ実行されていない）
    assert isinstance(result.output, DeferredToolRequests)
    assert [c.tool_name for c in result.output.approvals] == ["save_learning_log"]
    assert not _returns(result, "save_learning_log")


def test_approved_call_saves_file(log_dir):
    asked = []
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = run_with_approval(agent, "今日の学びを記録して",
                                   approve=lambda call: asked.append(call) or True)
    assert len(asked) == 1  # 利用者に1回だけ確認した
    assert isinstance(result.output, str)
    assert result.usage.requests == 2  # 承認前と承認後の両方を数えている
    assert len(list(log_dir.glob("*.md"))) == 1
    assert "保存しました" in str(_returns(result, "save_learning_log")[0].content)


def test_denied_call_does_not_save(log_dir):
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = run_with_approval(agent, "今日の学びを記録して", approve=lambda call: False)
    assert isinstance(result.output, str)
    assert not log_dir.exists() or not list(log_dir.glob("*.md"))
    # 拒否したことがモデルに伝わっている
    assert "許可しませんでした" in str(_returns(result, "save_learning_log")[0].content)
