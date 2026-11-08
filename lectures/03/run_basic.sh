#!/usr/bin/env bash
# 第3回 宿題（基礎）: INSTRUCTIONS / docstring を1か所ずつ変えて --trace で比べる。
# リポジトリの直下で実行する:  bash lectures/03/run_basic.sh
# 結果は lectures/03/logs/<条件>_<質問>_<回>.txt に保存される。終了時に app/ は元に戻る。
set -u
cd "$(git rev-parse --show-toplevel)"

if ! git diff --quiet -- app/; then
  echo "app/ に未コミットの変更があります。先にコミットか退避をしてください。" >&2
  exit 1
fi
trap 'git restore app/agent.py app/tools.py' EXIT

LOG_DIR=lectures/03/logs
mkdir -p "$LOG_DIR"
QUESTIONS=(
  "LoRAとQLoRAの違いは？"
  "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？"
)
RUNS=2
WAIT=10   # レート制限（429）を避けるための待ち時間（秒）

run_condition() {
  local name=$1
  echo "===== 条件: $name ====="
  for qi in "${!QUESTIONS[@]}"; do
    for r in $(seq 1 $RUNS); do
      local out="$LOG_DIR/${name}_q$((qi + 1))_run${r}.txt"
      echo "--- $name / Q$((qi + 1)) / run$r -> $out"
      uv run python -m app.agent --trace "${QUESTIONS[$qi]}" 2>&1 | tee "$out"
      sleep "$WAIT"
    done
  done
}

# 条件0: 元のまま
run_condition c0_base

# 条件1: INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を消す
sed -i '/必ず search_glossary で用語集を確認する/d' app/agent.py
git diff --stat -- app/
run_condition c1_no_must_search
git restore app/agent.py

# 条件2: docstring の「1つだけ入れる」を「まとめて入れる」に変える
sed -i 's/調べたい用語を1つだけ入れる/調べたい用語をまとめて入れる/' app/tools.py
git diff --stat -- app/
run_condition c2_docstring_bundle
git restore app/tools.py

echo "完了。ログ: $LOG_DIR"
