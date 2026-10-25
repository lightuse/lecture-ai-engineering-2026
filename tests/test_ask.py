import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors
from app.ask import chat_loop, show_response, temperature_value
from app.benchmark import run_benchmark


def response(text="ok", usage=None):
    return SimpleNamespace(text=text, usage_metadata=usage, model_version="actual-test-model")


def test_usage_missing_zero_and_empty_text(capsys):
    usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=None)
    assert show_response(response(None, usage), 0.25) == ""
    text = capsys.readouterr().out
    assert "[入力トークン数] 0" in text and "[出力トークン数] 不明" in text
    assert show_response(response(), 0) == "ok"


def test_chat_reuses_session_and_resets(monkeypatch):
    client = Mock()
    first, second = Mock(), Mock()
    first.send_message.return_value = response()
    second.send_message.return_value = response()
    client.chats.create.side_effect = [first, second]
    values = iter(["", "remember alpha", "what was it?", "/reset", "new", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    chat_loop(client)
    assert [c.args[0] for c in first.send_message.call_args_list] == ["remember alpha", "what was it?"]
    second.send_message.assert_called_once_with("new")
    assert client.chats.create.call_count == 2


def test_chat_api_error_and_eof(monkeypatch):
    client = Mock()
    client.chats.create.return_value.send_message.side_effect = errors.APIError(429, {"error": {"message": "quota"}})
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))
    chat_loop(client, first_question="hello")
    client.chats.create.return_value.send_message.assert_called_once_with("hello")


def test_benchmark_records_and_preserves_existing_file(tmp_path):
    client = Mock()
    client.models.generate_content.return_value = response("answer")
    path = tmp_path / "result.jsonl"
    kwargs = dict(models=["a", "b"], questions=["q"], repeats=3, temperature=1,
                  interval=0, output=path)
    assert run_benchmark(client, **kwargs)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 6
    assert all(r["response_model"] == "actual-test-model" for r in rows)
    assert [r["run"] for r in rows] == [1, 2, 3, 1, 2, 3]
    assert all(r["status"] == "ok" and r["answer"] == "answer" and r["seconds"] >= 0 for r in rows)
    with pytest.raises(FileExistsError):
        run_benchmark(client, **kwargs)
    assert client.models.generate_content.call_count == 6


def test_benchmark_stops_on_429(tmp_path):
    client = Mock()
    client.models.generate_content.side_effect = errors.APIError(429, {"error": {"message": "quota"}})
    path = tmp_path / "result.jsonl"
    assert not run_benchmark(client, models=["a"], questions=["q"], repeats=3,
                             temperature=1, interval=0, output=path)
    assert json.loads(path.read_text())["error_code"] == 429
    assert client.models.generate_content.call_count == 1


@pytest.mark.parametrize("value", ["-1", "3", "nan", "inf"])
def test_invalid_temperature(value):
    with pytest.raises(argparse.ArgumentTypeError):
        temperature_value(value)
