#!/usr/bin/env bash
# 第5回 宿題(基礎): RAG_TOP_K（通常のベクトル検索で返す件数）だけを変えて、同じ質問を --trace 付きで実行する。
# 使い方: bash lectures/05/run_basic.sh        （リポジトリ直下で実行。GEMINI_API_KEY が必要）
# app/config.py を一時的に書き換え、最後に git restore で戻す。app/ に未コミットの変更がある状態で実行しない。
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! git diff --quiet -- app/; then
  echo "app/ に未コミットの変更があります。commit するか戻してから実行してください。" >&2
  exit 1
fi
trap 'git restore app/config.py' EXIT

Q1='第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？'
Q2='第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか'
LOGDIR=lectures/05/logs
mkdir -p "$LOGDIR"

for K in ${TOP_KS:-5 2 10}; do
  sed -i "s/^RAG_TOP_K = .*/RAG_TOP_K = $K/" app/config.py
  for N in 1 2; do
    Q_VAR="Q$N"
    LOG="$LOGDIR/topk${K}_q${N}.log"
    echo "== RAG_TOP_K=$K / 質問$N -> $LOG"
    { echo "[RAG_TOP_K] $K"; echo "[question] ${!Q_VAR}"; PYDANTIC_AI_NO_BANNER=1 uv run python -m app.agent --trace "${!Q_VAR}"; } > "$LOG" 2>&1 || echo "  失敗（ログを確認）"
    sleep "${SLEEP_SECONDS:-20}"   # 無料枠のレート制限を避ける
  done
done
