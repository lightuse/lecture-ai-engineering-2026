#!/usr/bin/env bash
# 第5回 宿題(実装): 検索結果に前後1ページを付ける改良（AIE_RAG_NEIGHBORS=1）と、通常の検索（0）を同じ質問で比べる。
# 使い方: bash lectures/05/run_impl.sh        （リポジトリ直下で実行。GEMINI_API_KEY が必要）
# 環境変数で切り替えるだけで、ファイルは書き換えない。
set -euo pipefail
cd "$(dirname "$0")/../.."

QUESTIONS=(
  '第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？'
  '第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか'
  '第2回で、PEFTとLoRAを説明したあと、チャットボットでは何をFTし何をFTしないと説明していますか'
  '第3回で、エージェントが失敗しても「できた」と言ってしまう例は何ですか。それに対してどんな対策とその効果が示されていますか'
)
LOGDIR=lectures/05/logs
mkdir -p "$LOGDIR"

for N in "${!QUESTIONS[@]}"; do
  for NB in 0 1; do
    LOG="$LOGDIR/impl_nb${NB}_q$((N + 1)).log"
    echo "== 質問$((N + 1)) / 前後ページ=$NB -> $LOG"
    { echo "[AIE_RAG_NEIGHBORS] $NB"; echo "[question] ${QUESTIONS[$N]}"
      AIE_RAG_NEIGHBORS=$NB PYDANTIC_AI_NO_BANNER=1 uv run python -m app.agent --trace "${QUESTIONS[$N]}"; } > "$LOG" 2>&1 || echo "  失敗（ログを確認）"
    sleep "${SLEEP_SECONDS:-20}"   # 無料枠のレート制限を避ける
  done
done
