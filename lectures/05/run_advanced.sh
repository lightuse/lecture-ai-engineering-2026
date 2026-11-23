#!/usr/bin/env bash
# 第5回 宿題(発展): 用語ノードを入口にした取得（--term-map）と、基本RAG（通常のベクトル検索）を同じ質問で比べる。
# 使い方: bash lectures/05/run_advanced.sh        （リポジトリ直下で実行。GEMINI_API_KEY が必要）
set -euo pipefail
cd "$(dirname "$0")/../.."

QUESTIONS=(
  'MCPは第1回と第3回でそれぞれどのように説明されていますか'
  '構造化出力は第1回から第3回のどこで、どんな文脈で扱われていますか'
  '第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？'
  '第3回で、エージェントが失敗しても「できた」と言ってしまう例は何ですか。それに対してどんな対策とその効果が示されていますか'
)
LOGDIR=lectures/05/logs
mkdir -p "$LOGDIR"

for N in "${!QUESTIONS[@]}"; do
  for MODE in rag termmap; do
    FLAG=""; [ "$MODE" = termmap ] && FLAG="--term-map"
    LOG="$LOGDIR/adv_${MODE}_q$((N + 1)).log"
    echo "== 質問$((N + 1)) / $MODE -> $LOG"
    { echo "[mode] $MODE"; echo "[question] ${QUESTIONS[$N]}"
      AIE_RAG_NEIGHBORS=0 PYDANTIC_AI_NO_BANNER=1 uv run python -m app.agent $FLAG --trace "${QUESTIONS[$N]}"; } > "$LOG" 2>&1 || echo "  失敗（ログを確認）"
    sleep "${SLEEP_SECONDS:-20}"   # 無料枠のレート制限を避ける
  done
done
