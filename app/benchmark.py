"""同一質問を繰り返し、回答・使用量・API待ち時間をJSONLに記録する。"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep

from google import genai
from google.genai import errors

from app.ask import DEFAULT_QUESTION, generation_config, temperature_value, usage_counts
from app.config import MODEL, get_api_key


def run_benchmark(client, *, models, questions, repeats, temperature, interval, output):
    """既存の実測ファイルは上書きしない。429は記録して停止する。"""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    all_ok = True
    with output.open("x", encoding="utf-8") as stream:
        for model in models:
            for question in questions:
                for run in range(1, repeats + 1):
                    if count:
                        sleep(interval)
                    count += 1
                    row = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                               model=model, question=question, run=run,
                               temperature=temperature)
                    start = perf_counter()
                    try:
                        response = client.models.generate_content(
                            model=model, contents=question,
                            config=generation_config(temperature))
                    except errors.APIError as exc:
                        all_ok = False
                        row.update(status="error", error_code=exc.code,
                                   seconds=perf_counter() - start)
                    else:
                        row.update(status="ok", seconds=perf_counter() - start,
                                   answer=response.text or "",
                                   response_model=getattr(response, "model_version", None),
                                   **usage_counts(response))
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()
                    print(f"{count}: {model} run={run} {row['status']} "
                          f"{row['seconds']:.3f}s", flush=True)
                    if row.get("error_code") == 429:
                        print("429: レート制限を記録して停止しました。", flush=True)
                        return False
    return all_ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=[MODEL])
    parser.add_argument("--question", action="append", dest="questions")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--temperature", type=temperature_value, default=None)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or not 0 <= args.interval < float("inf"):
        parser.error("repeats は1以上、interval は有限の0以上が必要です")
    with genai.Client(api_key=get_api_key()) as client:
        ok = run_benchmark(client, models=args.models,
                           questions=args.questions or ["LoRAとは何ですか？", DEFAULT_QUESTION],
                           repeats=args.repeats, temperature=args.temperature,
                           interval=args.interval, output=args.output)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
