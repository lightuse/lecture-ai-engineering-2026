"""第1回: 単発質問、会話履歴、使用量・応答時間の計測。

uv run python -m app.ask "LoRAとは？" --temperature 1
uv run python -m app.ask --chat
"""
import argparse
from time import perf_counter

from google import genai
from google.genai import errors, types

from app.config import MODEL, api_error_message, get_api_key

DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def generation_config(temperature: float | None = None):
    return types.GenerateContentConfig(temperature=temperature)


def usage_counts(response) -> dict:
    usage = response.usage_metadata
    return {
        name: getattr(usage, name, None)
        for name in ("prompt_token_count", "candidates_token_count",
                     "thoughts_token_count", "total_token_count")
    }


def show_response(response, seconds: float) -> str:
    counts = usage_counts(response)
    for label, name in (("入力トークン数", "prompt_token_count"),
                        ("出力トークン数", "candidates_token_count")):
        value = counts[name]
        print(f"[{label}] {value if value is not None else '不明'}")
    print(f"[応答時間] {seconds:.3f} 秒")
    return response.text or ""


def ask(question: str, *, model: str = MODEL,
        temperature: float | None = None) -> str:
    with genai.Client(api_key=get_api_key()) as client:
        start = perf_counter()
        response = client.models.generate_content(
            model=model, contents=question, config=generation_config(temperature))
        return show_response(response, perf_counter() - start)


def chat_loop(client, *, model: str = MODEL,
              temperature: float | None = None, first_question: str | None = None):
    chat = client.chats.create(model=model, config=generation_config(temperature))
    print("会話を開始します。/exit で終了、/reset で履歴を消去します。")
    pending = first_question
    while True:
        try:
            question = pending if pending is not None else input("あなた> ")
            pending = None
        except (EOFError, KeyboardInterrupt):
            print("\n会話を終了します。")
            return
        question = question.strip()
        if question == "/exit":
            return
        if question == "/reset":
            chat = client.chats.create(model=model, config=generation_config(temperature))
            print("履歴を消去しました。")
            continue
        if not question:
            continue
        start = perf_counter()
        try:
            response = chat.send_message(question)
        except errors.APIError as exc:
            print(api_error_message(exc.code, exc.message))
            continue
        print(show_response(response, perf_counter() - start))


def temperature_value(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 2:
        raise argparse.ArgumentTypeError("temperature は 0〜2 を指定してください")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description="LLMへの質問と会話")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--temperature", type=temperature_value)
    parser.add_argument("--chat", action="store_true")
    args = parser.parse_args()
    print(f"[model] {args.model}")
    try:
        if args.chat:
            with genai.Client(api_key=get_api_key()) as client:
                chat_loop(client, model=args.model, temperature=args.temperature,
                          first_question=args.question)
        else:
            question = args.question or DEFAULT_QUESTION
            print(f"[質問] {question}\n")
            print(ask(question, model=args.model, temperature=args.temperature))
    except errors.APIError as exc:
        print(api_error_message(exc.code, exc.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
