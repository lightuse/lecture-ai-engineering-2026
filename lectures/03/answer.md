# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：
- `--trace` で見えたツール呼び出し（ツール名と引数）：
- 1つの質問での LLM 呼び出し回数（`requests`）：
- 追加したツールと、docstring に書いた説明：

## 宿題

- 取り組んだレベル：基礎、実装、発展（a）（b）

### 基礎：INSTRUCTIONS と docstring を変えて比べる

- やったこと：
  - 一度に1か所だけ変えて、同じ質問を `--trace` 付きで実行し比べた（モデル：gemini-3.5-flash-lite）。
    - c0：元のまま
    - c1：`app/agent.py` の INSTRUCTIONS から「用語や講座に固有のことを答える前に、必ず search_glossary で用語集を確認する。」の行を消す
    - c2：`app/tools.py` の `search_glossary` の docstring「調べたい用語を1つだけ入れる」を「調べたい用語をまとめて入れる」に変える
  - 質問は Q1「LoRAとQLoRAの違いは？」と Q2「AIE2026の講座で使う「lecNN-start タグ」とは何ですか？」。各条件・各質問を2回ずつ実行した（計12回）。
  - 実行は `lectures/03/run_basic.sh` で自動化し、ログを `lectures/03/logs/` に保存した。終わったら `app/` は元に戻している。
- 結果：

  | 条件 | Q1 のツール呼び出し | Q1 入力トークン | Q2 のツール呼び出し | Q2 入力トークン |
  |---|---|---|---|---|
  | c0 元のまま | `search_glossary('LoRA')`、`search_glossary('QLoRA')` の2回 | 1196 | `search_glossary('lecNN-start タグ')` の1回 | 783 |
  | c1 「必ず検索」を削除 | c0 と同じ2回 | 1148 | c0 と同じ1回 | 735 |
  | c2 「まとめて入れる」 | `search_glossary('LoRA QLoRA')` の1回 | 885 | c0 と同じ1回 | 779 |

  - 各条件の2回は、ツールの呼び方（回数・引数）が同じだった。`requests` はすべて2（ツールを呼ぶ1回と、結果を受けて答える1回）。
  - c1 の `--trace`（Q1）：INSTRUCTIONS から「必ず検索」を消しても検索している。
    ```
    [tool call]   search_glossary({'query': 'LoRA'})
    [tool call]   search_glossary({'query': 'QLoRA'})
    ```
  - c2 の `--trace`（Q1）：2つの用語を1回の呼び出しにまとめた。
    ```
    [tool call]   search_glossary({'query': 'LoRA QLoRA'})
    [usage] RunUsage(..., input_tokens=885, output_tokens=215, requests=2, tool_calls=1)
    ```
  - `search_glossary("LoRA QLoRA")` を直接呼ぶと、LoRA と QLoRA の両方が返った。検索語から空白を除いた "loraqlora" に、用語名 "lora"・"qlora" が含まれるので部分一致する。そのため c2 でも、回答に必要な定義はそろっていた。
  - 回答の中身（定義の内容、関係する回：Q1 は第2回、Q2 は第1回）は、どの条件でもほぼ同じで、違いは言い回しだけだった。
- 気づき・疑問：
  - INSTRUCTIONS の「必ず検索」を消しても、検索の回数は変わらなかった。docstring にも「答える前に使うこと」と書いてあるので、モデルはツールの説明だけを見て「使うべき」と判断していると考えられる。指示を書く場所が2か所あると、片方を消しても効果が残る。
  - docstring の1語（「1つだけ」→「まとめて」）で、ツール呼び出しの回数と引数がはっきり変わった。ツールをどう呼ぶかは、INSTRUCTIONS よりツールの docstring のほうが強く効いているように見える。
  - c2 ではツール呼び出しが1回減り、Q1 の入力トークンが 1196 → 885（約26%）減った。ただし、まとめて検索してうまくいったのは、今の部分一致の仕組みがたまたま合っていたから。直接試すと、「LoRA、QLoRA」や「LoRAとQLoRA」では両方ヒットしたが、「低ランク 量子化」では「量子化」しか返らなかった（「低ランク」は用語名ではなく、定義の中にある言葉のため）。検索語をまとめると、取りこぼしが起きる場合がある。
  - c2 の Q1 の回答には「Quantized LoRA」「劇的に削減」など、用語集にない言葉が出た。用語集の定義にモデル自身の知識が混ざっていると考えられる。「用語集にあることだけで答える」という制約は、今の INSTRUCTIONS では弱いのかもしれない。
  - 今回は各条件2回ずつで、毎回同じ呼び方だった。それでも温度などでぶれる可能性はあるので、回数を増やしたときに同じ傾向が出るかは確かめていない。
  - 疑問：Q2 のように、用語集にしか答えがない質問で「必ず検索」の指示と docstring の両方を消したら、検索せずに推測で答えるのか。

### 実装：保存の前に確認を挟む（save_learning_log）

- やったこと：
  - `app/tools.py` に `save_learning_log(title, content)` を作った。`learning_log/<日時>_<題名>.md` に Markdown を保存し、保存先を返す。
    - 題名の中の `/` や空白などはファイル名では `_` に置き換える。
    - 同じ名前のファイルがあっても上書きしない。
    - `learning_log/` は `.gitignore` 済み。
    - docstring には「利用者が記録を頼んだときだけ使う」と書いた。
  - `app/agent.py` の変更：
    - `agent.tool_plain(tools.save_learning_log, requires_approval=True)` で登録した。
    - `output_type=[str, DeferredToolRequests]` を加えた。
    - INSTRUCTIONS に「学んだことを記録するよう頼まれたら save_learning_log で保存する」を足した。
  - CLI の流れは `run_with_approval()` にまとめた。
    1. 実行して、結果が `DeferredToolRequests` なら、ツール名と引数を表示して「実行してよいですか？ [y/N]」と聞く。
    2. `y` なら `True`、それ以外なら `ToolDenied("利用者が実行を許可しませんでした。")` を `DeferredToolResults.approvals` に入れる。
    3. `message_history` と一緒に渡して続きを実行する。
    - 入力できない環境（EOF）では、安全側に倒して拒否する。
  - TestModel を使うテスト `tests/test_learning_log.py` を書いた（6件）。確かめたこと：
    - ファイルの保存
    - 上書きしないこと
    - 見出しが二重にならないこと
    - 承認待ちで止まること
    - 承認したときだけ保存されること
    - 拒否がモデルに伝わること
  - 既存の `tests/test_agent.py` の1件を直した。TestModel が全ツールを呼ぶと `save_learning_log` で承認待ちになって止まるので、基本の2ツールだけを呼ばせるようにした。全17件が通る。
- 結果（実際のモデルで実行。ログは `lectures/03/logs/impl_*.txt`）：

  | 質問 | 入力 | ツール呼び出し | 結果 |
  |---|---|---|---|
  | 「LoRAとQLoRAの違いを調べて、学習ログに記録して」 | `y` | search_glossary ×2 → save_learning_log ×1（requests=3） | `learning_log/` にファイルができた |
  | 同上 | `n` | search_glossary ×2 → save_learning_log ×1 | 保存されない。回答は「保存の実行がキャンセルされました」 |
  | 「LoRAとQLoRAの違いは？」（記録を頼まない） | なし | search_glossary ×2（requests=2） | 承認待ちにならない。save_learning_log は呼ばれない |

  承認待ちの表示（`y` のとき）：
  ```
  [承認待ち] save_learning_log を実行しようとしています。
    title: LoRAとQLoRAの違い
    content: # LoRAとQLoRAの違い
  ...
  実行してよいですか？ [y/N]
  [tool call]   save_learning_log({'title': 'LoRAとQLoRAの違い', 'content': '# LoRAとQLoRAの違い\n\n## LoRA（Low-Rank Adaptation）...'})
  [tool return] save_learning_log -> 保存しました: learning_log/20261109-000215_LoRAとQLoRAの違い.md…
  ```
  `n` のとき：
  ```
  [tool return] save_learning_log -> 利用者が実行を許可しませんでした。…
  ```
- 気づき・疑問：
  - 承認付きのツールが呼ばれると、ツール関数は実行されずに実行が止まる。`DeferredToolRequests` が返り、続きは「会話の履歴＋承認結果」を渡して改めて実行する仕組みだった。止まっている間にプログラム側で何をしてもよい（端末で聞く、Web で聞く、時間をおいて再開する）ので、人の確認とエージェントのループを切り離せる。
  - 拒否も「ツールの結果」としてモデルに返る。そのためモデルは「キャンセルされた」と説明して会話を続けられる。例外で止めるより自然。
  - 最初は `[usage]` に承認後の分（requests=1）しか出なかった。`run_sync` を2回呼んでいるため。`usage=result.usage` を渡して合計を数えるように直した。
  - 最初の実行では、モデルが本文の先頭にも `# 題名` を入れて、見出しが二重になった。docstring だけでは防げなかったので、ツール側で本文が `# ` で始まるときは見出しを足さないようにした。モデルの出力のぶれを、ツールの実装で吸収するのも大事だと思った。
  - ツールが1つ増えただけで、記録を頼まない同じ質問でも入力トークンが 1196 → 1550 に増えた。ツールの説明文は毎回モデルに送られるので、ツールを増やすとコストが上がる。
  - 既存のテストが「全ツールを呼ぶ」前提だったので、承認付きツールを足すと壊れた。承認付きのツールはテストの書き方にも影響する。
  - 疑問：承認の画面にはモデルが作った引数がそのまま出る。content が長いと確認が雑になりそうなので、要約や差分を見せるほうがよいのか。

### 発展（a）：エージェントを組み立てる部分だけを ADK で書き直す

- やったこと：
  - `adk_agent/glossary_agent/agent.py` と `__init__.py`（`from . import agent` の1行）を作った。
    - 指示は `app/agent.py` の INSTRUCTIONS、ツールは `app/tools.py` の `search_glossary`・`get_lecture_summary` をそのまま使った。モデルも `app/config.py` の `MODEL`（gemini-3.5-flash-lite）をそのまま使った。`make_quiz` はまだ作っていないので渡していない。
    - `app/` は変えていない。
  - 動作環境：google-adk 2.14.0。`PYTHONPATH=. uv run --with google-adk adk run adk_agent/glossary_agent` で動かした。
  - 演習と同じ2つの質問を、1問ごとに新しいセッションで聞いた。ツール呼び出しを見るために `adk run --in_memory --jsonl` で実行した。ログは `lectures/03/logs/adk_q*.jsonl` と `adk_run.txt`。
  - 書いたコード：
    ```python
    root_agent = Agent(
        model=MODEL,
        name="glossary_agent",
        description="AIE2026 の用語集と講義の要点を使って答える学習支援エージェント",
        instruction=INSTRUCTIONS,
        tools=[tools.search_glossary, tools.get_lecture_summary],
    )
    ```
- 結果：
  - 書き方の違い：

    | 項目 | Pydantic AI（演習） | ADK |
    |---|---|---|
    | 指示の渡し方 | `Agent(instructions=INSTRUCTIONS)` | `Agent(instruction=INSTRUCTIONS)`（単数形）。`{変数名}` はセッション状態（state）の値に置き換わる（今の INSTRUCTIONS には `{` がないので影響なし） |
    | ツールの渡し方 | `agent.tool_plain(関数)` で後から1つずつ登録する | `tools=[関数, ...]` でまとめて渡す。どちらも docstring と型ヒントからツールの説明が作られるので、関数は書き換えずに使えた |
    | モデル | 実行時に `run_sync(..., model=GoogleModel(...))` で渡す（テストで TestModel に差し替えるため） | `model="gemini-3.5-flash-lite"` と文字列で、組み立てるときに決める |
    | 名前 | なくてもよい | `name` が必須。`description` もある |
    | APIキー | `app/config.py` で環境変数 `GEMINI_API_KEY` を読む（`.env` は読まない） | `adk run` が `.env` を自動で読む（ログに `Loaded .env file ... /.env`） |
    | 動かし方 | 自分で書いた CLI（argparse）。1回の質問で終わる | `adk run` が対話の画面とセッションを用意する。同じセッションの中では会話が続く |
    | ツール呼び出しの見え方 | 自分で書いた `--trace` | `--jsonl` のイベント（`functionCall` / `functionResponse`）。ツールの戻り値は `{"result": ...}` に包まれる |
    | フレームワークが足す指示 | なし（INSTRUCTIONS とツールの説明だけ） | `You are an agent. Your internal name is "glossary_agent". The description about you is "..."` が自動で足される（ADK のソース `flows/llm_flows/prompt/_identity.py` で確認） |

  - 同じ質問への回答の違い（Pydantic AI 側は基礎の c0 の結果）：

    | 質問 | ツール呼び出し（Pydantic AI → ADK） | 入力トークン（Pydantic AI → ADK） | 回答 |
    |---|---|---|---|
    | Q1 LoRAとQLoRAの違いは？ | `search_glossary('LoRA')`、`('QLoRA')` の2回 → **同じ** | 1196 → 1390（requests=2） | ほぼ同じ内容。ADK でも用語集の定義をもとに答え、最後に「関係する回：第2回」 |
    | Q2 lecNN-start タグとは？ | `search_glossary('lecNN-start タグ')` の1回 → **同じ** | 783 → 979（requests=2） | ほぼ同じ内容。最後に「第1回」 |

  - 記録を頼んだとき（「LoRAを調べて、学習ログに記録して」）：
    ```
    [tool call] search_glossary {'query': 'LoRA'}
    [tool call] search_glossary {'query': '学習ログ'}
    [tool call] search_glossary {'query': 'save_learning_log'}
    [tool return] search_glossary {'result': '用語集に「save_learning_log」は見つかりませんでした。'}
    → 「（学習ログの保存は）今回は私のほうで直接保存することはできません」と回答（requests=4）
    ```
- 気づき・疑問：
  - 指示とツール関数がフレームワークに依存しないので、組み立てる部分の十数行を書き直すだけで ADK に移せた。モデルは同じなので、ツールの呼ばれ方も回答もほぼ変わらなかった。エージェントの振る舞いを決めているのは、フレームワークよりも「モデル＋指示＋ツールの説明」だと実感した。
  - 入力トークンは、モデルを1回呼ぶごとに ADK のほうが約100多かった（Q1 は2回呼んで +194、Q2 は2回呼んで +196）。ADK が足す名前と description の指示が原因と考えられる。ただし、今の INSTRUCTIONS には実装レベルで足した1行が入っているので、その分も含まれている。フレームワークが見えないところでプロンプトを足していることは、ソースを読むまで分からなかった。
  - 実装レベルで INSTRUCTIONS に「save_learning_log で保存する」と書いたが、ADK 版にはそのツールを渡していない。そのため記録を頼むと、モデルが `save_learning_log` を「用語」として用語集で検索した（無駄なツール呼び出しが2回）。指示に書いたツールと実際に渡したツールが食い違うと、モデルは迷って余計な行動をとる。INSTRUCTIONS を共有するなら、ツールの組み合わせも揃える必要がある。
  - Pydantic AI はモデルを実行時に渡すので、TestModel に差し替えたテストが書きやすい。ADK は `adk run` や `adk web` などの実行環境とセッション管理が最初から付いていて、対話で試すのが楽だった。
  - 疑問：ADK で承認付きのツール（Pydantic AI の `requires_approval=True` にあたるもの）を作るにはどうするのか。今回は作っていない。

### 発展（b）：Pi のシステムプロンプトと自分の INSTRUCTIONS を比べる

- やったこと：
  - Pi のシステムプロンプトを組み立てるコード `packages/coding-agent/src/core/system-prompt.ts` を読んだ（commit `705d047cb5`、2026-10-31）。
  - ツールごとに差し込まれる説明文を見るため、標準ツール（read / bash / edit / write）の定義 `src/core/tools/*.ts` も読んだ。
  - Pi を Codespaces で動かした（インストール → `pi` → `/model` で Gemini を選ぶ）。`search_glossary` の仕組みの説明と、テストの追加を頼み、終わったあと `git status` / `git diff` で何が変わったかを確かめた。
- 結果：
  - Pi のシステムプロンプトは固定の文章ではなく、`buildSystemPromptSections()` が部品を組み立てて作る。標準の4ツールで、プロジェクトの指示ファイルやスキルがないときは、だいたい次の形になる（ソースから組み立てたもの。実際の出力は見ていない）。
    ```
    You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.
    <tools>
    - read: Read file contents
    - bash: Execute bash commands (ls, grep, find, etc.)
    - edit: Make precise file edits with exact text replacement, including multiple disjoint edits in one call
    - write: Create or overwrite files

    Additional tools may be available.
    </tools>
    <rules>
    - Use bash for file operations like ls, rg, find
    - Use read to examine files instead of cat or sed.
    - You can inspect PI_* environment variables for current model and session details.
    - Use edit for targeted changes. Batch changes to one file in a single call.
    - Each edits[].oldText must exactly and uniquely match the original file. ...
    - Use write only for new files or complete rewrites.
    - Be concise in your responses
    - Show file paths clearly when working with files
    </rules>
    <docs>（Pi 自身のドキュメントの場所と、「Pi について聞かれたときだけ読む」という指示）</docs>
    <cwd>（作業ディレクトリ）</cwd>
    ```
    - 加えて、設定があれば `<addendum>`（利用者が足す文）、`<project_context>`（プロジェクトの指示ファイル）、`<skills>` が差し込まれる。設定でプロンプト全体を置き換えることもできる（`customPrompt` / `forceSystemPrompt`）。
  - 比較：

    | 観点 | Pi | 自分の INSTRUCTIONS |
    |---|---|---|
    | 役割 | 「pi の中で動くコーディング支援。ファイルを調べ、コマンドを実行し、コードを直す」 | 「AIE2026 の学習支援エージェント」 |
    | ツールの一覧 | `<tools>` にツール名と1行の説明を並べる | 書いていない（ツールの説明は docstring に任せる） |
    | ツールの使い分け | ある（「cat や sed ではなく read を使う」「write は新規作成か全体の書き直しだけ」など） | ある（「答える前に必ず search_glossary」「回の内容は get_lecture_summary」） |
    | 答え方 | 「簡潔に答える」「ファイルのパスをはっきり示す」 | 「最後に関係する回（第N回）を示す」 |
    | 根拠と推測 | **書いていない** | 「用語集にないことは推測で断定せず、ないと伝える」 |
    | 教育上の方針 | なし | 「宿題の答えは書かず、ヒントで導く」 |
    | 安全・確認 | **書いていない**（危険なコマンドの前に確認する、などの指示はない） | 書いていない（確認は `requires_approval=True` でコード側に持たせた） |
    | 環境の情報 | 作業ディレクトリ（cwd）、Pi のドキュメントの場所、`PI_*` 環境変数 | なし |
    | プロジェクト固有の指示 | 指示ファイル・スキル・追記文を後から差し込める | INSTRUCTIONS に直接書く |
    | 構造 | セクションごとに XML タグで囲む。変わったセクションだけを差分で送り直せる（`diffSystemPromptSections`） | 箇条書き6行のひとつながりの文字列 |
- 気づき・疑問：
  - Pi のプロンプトはかなり短く、汎用的。「何をするか」は役割の1文だけで、あとはツールの使い方と答え方の短いルール。プロジェクト固有のことは指示ファイルやスキルで後から足す前提になっている。自分の INSTRUCTIONS は逆で、ドメインの決まり（用語集を根拠にする・推測しない・宿題の答えを書かない）が中心。
  - Pi では、ツールごとのルール（`promptGuidelines`）がツールの定義と同じファイルに書かれている。システムプロンプトには **選ばれたツールのルールだけ** が入る（`buildRules` が `selectedTools` の分だけ足す）。発展（a）では、INSTRUCTIONS に書いた `save_learning_log` が ADK 版になく、モデルが迷った。Pi のやり方なら、ツールを外せばそのルールも一緒に消えるので、この食い違いが起きない。基礎で分かった「ツールの使い方は docstring が強く効く」こととも合う。ツールの使い方はツールの側に書くのがよい。
  - Pi のプロンプトには「推測しない」「危険な操作の前に確認する」といった安全の指示が一つもない。資料にある「Pi は確認を求めずにファイルの書き換えやコマンドの実行を行う」とも一致する。確認は、プロンプトでお願いするより、実装で強制する（実装レベルの `requires_approval=True` のように）ほうが確実だと思う。
  - 「Pi のドキュメントは、Pi について聞かれたときだけ読む」と、いつ使うかを条件付きで書いている。自分の INSTRUCTIONS の「回の内容を聞かれたら get_lecture_summary を使う」と同じ書き方。
  - 疑問：Pi で Gemini を使うとき、このプロンプトのほかにモデルごとの文が足されるのか。`getSystemMessageText` は別のパッケージ（pi-ai）にあり、そこは読んでいない。
- Pi を動かした結果（Codespaces、`main` ブランチ）：
  - 使ったモデル：gemini-3.5-flash-lite（演習と同じ）
  - 頼んだこと（1つのセッションで続けて）：
    1. 「app/tools.py の search_glossary の仕組みを説明して」
    2. 「app/tools.py の search_glossary にテストを1つ足して」
  - Pi が呼んだツール（画面の表示から）：

    | 依頼 | ツール呼び出しの順番 | 確認を求められたか |
    |---|---|---|
    | 1. 説明して | `read app/tools.py:1-2000` の1回 → 日本語で説明 | なし（読むだけ） |
    | 2. テストを足して | `$ pytest`（15 passed）→ `read tests/test_tools.py` → `read data/glossary.json:1-100` → `edit tests/test_tools.py` → `$ pytest`（16 passed）→ `$ git diff` | **なし**。ファイルの書き換えも、`pytest` や `git diff` のコマンド実行も、聞かれずに行われた |

  - 1 の説明は、正規化（`_normalize`）、3段階の検索（exact → partial → in_definition）、最大3件、見つからないときのメッセージ、という流れをおおむね正しく捉えていた。ただし、コードと照らすと不正確なところが2か所あった。
    - 「exact は完全に一致（**または含まれる**）」と書いているが、`q in _names(e)` はリストの要素との完全一致なので「含まれる」は誤り。
    - partial の説明は「クエリが名前の部分文字列に含まれる」方向だけで、「名前（3文字以上）がクエリに含まれる」方向（`n in q`）が抜けている。基礎の c2 で `"LoRA QLoRA"` が両方ヒットしたのは、この抜けている方向のおかげ。
  - 変わったもの（`git status` / `git diff`）：`tests/test_tools.py` だけが変更され、空の検索語のテストが1つ足された。ほかのファイルは変わっていない。
    ```diff
    +def test_search_empty_query():
    +    assert "検索語が空です" in tools.search_glossary("")
    +    assert "検索語が空です" in tools.search_glossary("   ")
    ```
  - 足されたテストが正しいかを、手元で `search_glossary("")` と `search_glossary("   ")` を呼んで確かめた。どちらも「検索語が空です。調べたい用語を1つ指定してください。」が返るので、テストの期待は合っている。
  - 気づき：
    - 2 では、頼んでいないのに「書き換える前に pytest で今の状態を確かめる → 書き換える → もう一度 pytest → git diff で変更を見せる」という流れをとった。システムプロンプトには「テストを実行せよ」とは書いていないので、モデル自身がコーディングエージェントとしての振る舞いを身につけていると考えられる。プロンプトは短くても、手順の多くはモデルに任せられている。
    - 読むときは `cat` ではなく `read`、書き換えは `write` ではなく `edit` を使い、コマンドの実行（pytest・git）だけに bash を使った。システムプロンプトの rules（「Use read to examine files instead of cat or sed」「Use edit for targeted changes」）のとおりに使い分けていた。
    - 「Be concise」とあるのに、1 の説明は見出し付きでかなり長かった。「仕組みを説明して」と頼まれたので詳しく書いたのだと思うが、短い指示だけでは答え方の長さは決めきれない。
    - 説明は一見もっともらしいが、細かい条件（完全一致か部分一致か、どちら向きの部分一致か）を間違えていた。コードを読んだうえでの説明でも、そのまま信じず、元のコードと照らして確かめる必要がある。自分の INSTRUCTIONS の「推測で断定しない」に当たる指示は Pi にはない。
    - 途中の思考の表示には「query と definition の検索関数の両方に空文字を渡す」とあったが、そういう関数は別にない。実際に書いたテストは `search_glossary` だけを呼んでいた。思考の表示と実際の行動は、ずれることがある。
    - Pi は、既存のテストに足りなかった「空の検索語」の場合を見つけて、既存のテストと同じ書き方（`assert "..." in tools.search_glossary(...)`）で足した。`search_glossary` の中の `if not q:` の分岐を読んで、テストのない分岐を選んだと考えられる。プロンプトの「Use edit for targeted changes」のとおり、既存ファイルへの小さな差し込みになっている。
    - 空白だけの `"   "` も試しているのは、`_normalize` が空白を取り除くことまで読んだからだと思われる。ただし全角の空白（`"　"`）は試していない。
    - 変更が1ファイル・5行に収まっていたので `git diff` ですぐ確認できた。確認なしで書き換えるエージェントを使うときは、git で差分を見て戻せる状態で使うことが前提になると思った。
