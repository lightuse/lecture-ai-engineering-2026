# AGENTS.md

このリポジトリで作業する AI コーディングエージェント（Claude Code / Copilot / Codex など）向けの指示です。
人間向けの説明は [README.md](README.md) を参照してください。

## プロジェクトの概要

- AIエンジニアリング実践講座（AIE2026）の演習・宿題用リポジトリ。
- 講座を通して「AIエンジニアリングの学習を支援するエージェント」を回ごとに育てていく。
- 回ごとに作業ブランチ（例: `lec03`）を切り、`lectures/NN/answer.md` に記入して、fork 内で `main` への PR を作って提出する。

## 環境とコマンド

- Python 3.12、パッケージ管理は **uv**。依存は `uv.lock` で固定されている。

```bash
uv sync --frozen                                   # 依存を入れる（lock を更新しない）
uv run pytest -q                                   # テスト（API キー不要）
uv run python -m app.ask "LoRAとは何ですか？"        # 第1回: LLM に質問
uv run python -m app.agent --trace "LoRAとQLoRAの違いは？"   # 第3回: エージェント（ツール呼び出しを表示）
uv run python -m app.agent --mcp --list-tools      # 第5回: MCP 経由のツール一覧（API キー不要）
uv run python -m app.mcp_server --http             # 第5回: MCP サーバーを HTTP で起動
PYTHONPATH=. uv run --with google-adk adk run adk_agent/glossary_agent   # 第3回 発展(a): ADK 版
```

- 既定モデルは `gemini-3.5-flash-lite`。環境変数 `AIE_MODEL` で切り替える（[app/config.py](app/config.py)）。
- LLM を呼ぶコマンドは環境変数 `GEMINI_API_KEY` が必要。無料枠のレート制限があるので、**LLM を呼ぶコマンドを無駄に繰り返さない**。429 が出たら 1 分ほど待つ。

## 構成

| パス | 内容 |
|---|---|
| `app/config.py` | モデル名・API キーの読み込み、API エラーの日本語メッセージ |
| `app/ask.py` | 第1回: LLM に質問する CLI |
| `app/tools.py` | 第3回: エージェントのツール（`search_glossary` / `get_lecture_summary` / `save_learning_log`） |
| `app/agent.py` | 第3回: Pydantic AI の学習支援エージェント。`INSTRUCTIONS` とツール登録、承認フロー、`--mcp` |
| `app/mcp_server.py`, `app/mcp_servers.json` | 第5回: 用語集を公開する MCP サーバーとその設定（`mcpServers` 形式） |
| `adk_agent/glossary_agent/` | 第3回 発展(a): 同じ指示・ツールを Google ADK で組み直したもの |
| `data/glossary.json`, `data/lectures/NN.md` | 用語集と各回の要点（ツールが読むデータ） |
| `lectures/NN/problem.md` | 各回の演習・宿題の問題文（**編集しない**） |
| `lectures/NN/answer.md` | 受講生が記入する提出物 |
| `lectures/03/run_basic.sh`, `lectures/03/logs/` | 第3回 宿題(基礎): 条件を変えた比較実行スクリプトと実行ログ |
| `notebooks/` | 第2回: Colab で動かす LoRA ノートブック |
| `scripts/` | 補助スクリプト（SFT データセット作成など） |
| `tests/` | pytest。`TestModel` を使い LLM を呼ばない |

## 守ること

### 秘密情報
- API キーをコード・コミット・ログ・answer.md に**絶対に書かない**。キーは環境変数 `GEMINI_API_KEY` からのみ読む。
- `.env` / `.env.*` はコミットしない（`.gitignore` 済み）。中身を表示・引用しない。

### 依存関係
- 依存パッケージの版は講座期間中は固定。**`pyproject.toml` / `uv.lock` を勝手に更新しない**（`uv add` や `uv lock --upgrade` をしない）。
- 一時的に追加パッケージが必要なら `uv run --with <pkg>` を使う（ADK 版と同じやり方）。

### コード
- コメント・docstring・ユーザー向けメッセージは**日本語**で書く（既存コードに合わせる）。
- ツール関数の docstring と型ヒントは、モデルに渡るツール説明になる。変更するとエージェントの挙動が変わるので、意図して変えるときだけ触る。
- エージェントの `INSTRUCTIONS` は `app/agent.py` にあり、ADK 版からも import される。変更すると両方に効く。
- モデルは実行時に渡す設計（テストで `TestModel` に差し替えるため）。モジュール読み込み時に API キーを要求するコードにしない。
- ファイル保存のように取り消しにくいツールは `requires_approval=True` で登録する。
- `TODO(第N回 ...)` は受講生が取り組む箇所。頼まれない限り埋めない。

### 学習目的への配慮
- これは学習用リポジトリ。受講生が自分で取り組むべき宿題の答え（`answer.md` の考察など）を、頼まれていないのに丸ごと書かない。
- `lectures/NN/problem.md` と `data/` は講座側の配布物なので、明示的に頼まれない限り編集しない。
- `learning_log/` は個人の学習ログで共有しない（`.gitignore` 済み）。

### 作業後の確認
- 変更後は `uv run pytest -q` を通す。
- `lectures/03/run_basic.sh` は `app/agent.py` / `app/tools.py` を一時的に書き換えて最後に `git restore` で戻す。`app/` に未コミットの変更がある状態で実行しない。

### Git
- コミットや push は頼まれたときだけ行う。`main` に直接コミットせず、回ごとの作業ブランチで作業する。
- コミットメッセージは日本語でよい（既存履歴に合わせる）。
