# 第6回 解答

## 演習

<!-- [tool call] の行は、表示された行をそのまま貼り付けてください。終わらなかった STEP は、空欄のままでかまいません。 -->

- STEP 1 のツールの名前：glossary_search_glossary
- STEP 2 の [tool call]：glossary_search_glossary({'query': '3レベル'})
- STEP 3 の [tool call]：fetch_fetch({'url': 'https://modelcontextprotocol.io/'})
- STEP 4 の [tool call]：aws_aws___search_documentation({'topics': ['general'], 'search_phrase': 'Amazon S3 バージョニング'})、aws_aws___search_documentation({'search_phrase': 'Using versioning in S3 buckets', 'topics': ['general']})
- 気づき・疑問：
  - 気づき：`app/mcp_servers.json` に数行足しただけで、エージェントのコードを変えずにツールが 1 個から 7 個（glossary 1・fetch 1・aws 5）に増えた。ツールの名前は「サーバー名_ツール名」になるが、AWS はサーバー側のツール名がもともと `aws___` で始まるため、`aws_aws___search_documentation` と接頭辞が重なった。
  - 気づき：STEP 4 では検索が 2 回呼ばれた。1 回目は日本語の `Amazon S3 バージョニング` で検索して関係の薄い記事が先頭に返り、2 回目にモデルが自分で英語の `Using versioning in S3 buckets` に言い換えて検索し直していた。ツールの結果を見て引数を変える動きを trace で確認できた。
  - 気づき：入力トークンは STEP 2 が 709、STEP 3 が 2,173、STEP 4 が 11,106 だった。ツールの数と、ツールが返す内容の量が増えると、入力トークンが大きく増える。
  - 疑問：サーバーを足すほど、使わないツールの説明文も毎回モデルに渡ることになる。ツールが数十個になったとき、質問に必要なツールだけを渡す方法はあるのか。
  - 疑問：fetch や AWS の説明文は英語で、作者が書いたものがそのままモデルに渡る。説明文に不適切な指示が書かれていた場合、エージェント側で気づいたり防いだりする手段はあるのか。

## 宿題

<!-- 基礎・実装・発展のどれか1つに取り組めば完了です。 -->

### 基礎

- 取り組んだレベル：基礎
- やったこと：
  - `app/mcp_server.py` の `TODO(宿題・基礎)` の下に `server.tool()(tools.get_lecture_summary)` の 1 行を書き足した。エージェント側（`app/mcp_servers.json`、`app/mcp_agent.py`）は、宿題では変えていない。
  - `uv run python -m app.mcp_agent --list-tools` でツールの一覧を表示した。
  - `uv run python -m app.mcp_agent --trace "第2回では何を学びますか？"` で質問した。
  - `uv run pytest -q` を実行した。
- 結果：
  - 一覧のツールが 7 個から 8 個に増え、`glossary_get_lecture_summary`（引数: `{"lecture": {"title": "Lecture", "type": "integer"}}`）が表示された。
  - 質問では `[tool call]   glossary_get_lecture_summary({'lecture': 2})` が呼ばれ、`[tool return]` に第2回の要点（`# 第2回 ファインチューニングとLoRA …`）が返り、それをもとに回答された。モデル応答は 2 回、入力は 5,932 tokens だった。
  - テストは 21 件すべて通った。
- 気づき・疑問：
  - 気づき：サーバー側に 1 行足しただけで、エージェント側を変えずにツールが増えた。エージェントが起動のたびにサーバーへツールの一覧を問い合わせているためで、ツールを「公開する側」と「使う側」が分かれていることを確認できた。
  - 気づき：説明文と引数の型は、第3回の `app/tools.py` の docstring と型ヒントがそのまま使われていた。質問の「第2回」から、モデルが `lecture` に整数の 2 を入れている。同じ関数を、直接登録する方法（第3回）と MCP で公開する方法（第6回）の両方で使い回せる。
  - 疑問：逆に言うと、サーバー側がツールを足したり説明文を変えたりすると、エージェント側は何も変えていなくても挙動が変わる。外部のサーバーで版を固定する（`==2026.11.11`）のはこのためだと思うが、URL で接続するサーバー（aws）は版を固定できない。その場合の変化には、どう備えるのか。

### 実装

- 取り組んだレベル：実装
- やったこと：
  - 第3回で `make_quiz` を作っていなかったので、`app/mcp_server.py` に新しく `make_quiz(lecture: int, num_questions: int = 3)` を書き、`@server.tool()` を付けて公開した。指定した回の用語集の用語から、「〜とは何か、説明してください。」という問題と模範解答（定義）を JSON で返す。
  - 引数が範囲外のときは、例外にせず、次にどうすればよいかが分かるメッセージを `return` で返すようにした。用語集に用語がない回（例：第99回）には「クイズを作れる回」の一覧を、問題数が 1〜5 の外のときには指定できる範囲を返す。
  - `uv run python -m app.mcp_agent --trace "第99回のクイズを作って"` で、メッセージがモデルにどう伝わるかを確認した。
  - 比べるために、同じ箇所を一時的に `raise ValueError(...)` に書き換えて同じ質問をし、確認後に `return` に戻した。
  - `tests/test_mcp_server.py` に、正常な回と範囲外の引数のテストを 2 件足した。
- 結果：
  - 一覧に `glossary_make_quiz`（引数: `lecture` は integer、`num_questions` は integer で default 3）が増えた。
  - `return` の場合：`[tool call]   glossary_make_quiz({'lecture': 99})` のあと、`[tool return] glossary_make_quiz -> 第99回のクイズは作れません。用語集に第99回の用語がないためです。クイズを作れる回: 1, 2, 3, 4, 6。lecture にはこのどれかを指定してください。` と出た。モデルの回答は「クイズを作成できるのは第1、2、3、4、6回です。どの回のクイズをご希望でしょうか？」で、メッセージの内容がそのまま使われた。モデル応答 2 回、入力 5,711 tokens。
  - `raise` の場合：`[tool error]  glossary_make_quiz -> Error executing tool make_quiz` と出た。`ValueError` に書いたメッセージは trace に出ず、モデルの回答も「第99回という回は範囲に存在しないため作成できません」までで、作れる回の一覧は答えに入らなかった。モデル応答 2 回、入力 5,672 tokens。
  - テストは 23 件すべて通った。
- 気づき・疑問：
  - 気づき：`return` で返したメッセージは、ツールの結果としてそのままモデルに渡り、モデルはそれを読んで利用者に「どの回なら作れるか」を案内できた。メッセージは、人ではなくモデルが次の行動を決めるための材料になるので、「何がだめか」だけでなく「何を指定すればよいか」まで書くと役に立つ。
  - 気づき：`raise` にすると、今回の構成ではモデルに渡ったのは「ツールの実行に失敗した」という内容だけで、例外に書いた理由は伝わらなかった。そのため回答から、作れる回の一覧が抜けた。範囲外のように「起こり得る入力」は、例外ではなく `return` で説明するほうがよい。
  - 気づき：今回はどちらの場合もモデルは呼び直さず、2 回の応答で終わった。第99回は言い換えても存在しないので、呼び直さないのは妥当な動きだった。
  - 疑問：`raise` のときに例外のメッセージが `Error executing tool make_quiz` に置き換わるのは、MCP サーバー側の仕様なのか、クライアント（Pydantic AI）側の仕様なのか。内部の情報を外に漏らさないための既定の動作だとすれば、モデルに伝えたいエラーと隠したいエラーを、どう書き分けるのがよいのか。

### 発展

- 取り組んだレベル：発展
- やったこと：
  - 自分が使っている Claude Code（CLI、手元の版は 2.1.318）を選び、MCP サーバーの設定方法を公式ドキュメントで調べた。
  - 調べた日付：2026-11-23
  - 参照した公式ドキュメント：https://code.claude.com/docs/en/mcp （日本語版 https://code.claude.com/docs/ja/mcp ）
  - ドキュメントの内容を、手元で `claude mcp --help` と `claude mcp add --help` を実行して照らし合わせた（サーバーの登録はしていない）。
  - 調べた設定方法を、演習で使った `app/mcp_servers.json` と比べた。
- 結果：

  | 調べること | 演習の `app/mcp_servers.json` | Claude Code |
  |---|---|---|
  | 設定を書く場所 | `app/mcp_servers.json` の 1 ファイル。手で書く | スコープで決まる。project は、プロジェクトのルートの `.mcp.json`。local と user は `~/.claude.json`。手で書くほかに、`claude mcp add` や `claude mcp add-json <name> '<json>'` で登録できる。確認は `claude mcp list` / `claude mcp get <name>`、削除は `claude mcp remove <name>` |
  | コマンドで起動する書き方 | `"glossary": {"command": "uv", "args": ["run", "python", "-m", "app.mcp_server"]}` | `.mcp.json` では同じ `mcpServers` / `command` / `args`（加えて `env`）で書く。コマンドでは `claude mcp add [options] <name> -- <command> [args...]`。`--` より前が Claude Code のオプション、後ろがサーバーを起動するコマンド。例：`claude mcp add my-server -e API_KEY=xxx -- npx my-mcp-server` |
  | URL で接続する書き方 | `"aws": {"url": "https://knowledge-mcp.global.api.aws"}`（`url` だけ） | `.mcp.json` では `{"type": "http", "url": "https://example.com/mcp"}`。`type` のない項目は stdio として読まれるので、`url` だけでは設定の誤りになる。認証などは `"headers"` に書ける。コマンドでは `claude mcp add --transport http <name> <url>`（`--header` でヘッダーを付ける）。SSE は非推奨で、HTTP を使うよう書かれている |
  | 有効になる範囲 | このリポジトリの `app.mcp_agent` を実行したときだけ | local（既定）：そのプロジェクトで自分だけ。project：`.mcp.json` をバージョン管理に入れて、そのプロジェクトをチームで共有。user：自分のすべてのプロジェクト。`--scope`（`-s`）で選ぶ。同じ名前のサーバーがあるときは local → project → user の順に優先される |

  - 手元の `claude mcp add --help` でも、`-s, --scope <scope>  Configuration scope (local, user, or project) (default: "local")` と `-t, --transport <transport>  Transport type (stdio, sse, http). Defaults to stdio if not specified.` と表示され、ドキュメントの記載と一致した。
  - そのほかの違い：
    - project スコープ（`.mcp.json`）のサーバーは、使う前に対話セッションで承認を求められる。演習のエージェントは、設定ファイルに書いたサーバーを確認なしに起動・接続する。
    - `.mcp.json` では `${VAR}` と `${VAR:-default}` で環境変数を展開できる。演習の設定ファイルには、この仕組みがない。
    - モデルに見えるツールの名前は `mcp__<server>__<tool>` の形になる。演習では `<server>_<tool>`（例：`glossary_search_glossary`）だった。
- 気づき・疑問：
  - 気づき：コマンドで起動するサーバーの書き方は、`mcpServers` / `command` / `args` というキーまで演習と同じだった。演習の `glossary` の設定は、そのまま `.mcp.json` に書ける形をしている。一方、URL で接続する書き方は `"type": "http"` が要る点が違い、演習の `aws` の 1 行をそのまま写すと誤りになる。「`mcpServers` 形式」は共通でも、細部はソフトウェアごとに確かめる必要がある。
  - 気づき：Claude Code では「誰に・どこまで有効か」を 3 つのスコープで分けている。演習の補足にあった「信頼できるサーバーか確認してから足す」という考え方が、project スコープの承認という形で仕組みになっている。リポジトリを clone しただけで、書かれていたサーバーが勝手に起動することを防ぐためだと理解した。
  - 気づき：API キーのような秘密情報は、チームで共有する `.mcp.json` に直接書かず、`${VAR}` で環境変数から読ませる書き方が用意されている。この講座で `GEMINI_API_KEY` を環境変数からだけ読むのと同じ考え方である。
  - 疑問：local と user はどちらも `~/.claude.json` に保存される。同じファイルの中でどう区別されているのか（local は「そのプロジェクトのパスの下」に保存されると書かれていた）。また、Codex や Gemini CLI、VS Code では、ファイル名やキーの名前がどこまで共通なのかを、次に比べてみたい。

