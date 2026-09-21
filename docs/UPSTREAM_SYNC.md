# 原典（upstream）からの変更取り込み手順

このドキュメントは、本リポジトリ（petadimensionlab 版）に原典プロジェクト
`aiming-lab/AutoResearchClaw` の改善を安全に取り込むための実務手順をまとめたものです。
コマンドはすべてこのリポジトリの現在のリモート構成に合わせており、そのままコピー&ペーストできます。

---

## 1. 目的と方針

- このリポジトリは `aiming-lab/AutoResearchClaw`（以下 **原典**）から派生した
  petadimensionlab 独立版です。原典側の改善・バグ修正を今後も取り込んでいきます。
- 方針は **`git merge` 方式** です。`main` への **force-push は禁止**します。
  公開リポジトリのため、履歴の改変は行いません。
- `rebase` は**非推奨**です（理由と限定的な使い方は [7. 代替方式: rebase（非推奨）](#7-代替方式-rebase非推奨) を参照）。

---

## 2. 現在のリモート構成

| リモート | URL | 役割 |
|---|---|---|
| `origin` | `https://github.com/petadimensionlab/AutoResearchClaw.git` | 本リポジトリ（public） |
| `upstream` | `https://github.com/aiming-lab/AutoResearchClaw.git` | 原典（参照・取り込み元のみ。**push 禁止**） |

- ローカルの `main` は `origin/main` を追跡しています。
- 原典には**書き込み権限がありません**。`git push upstream ...` は**絶対に行わない**でください。
  `upstream` は私たちにとって**読み取り専用**です。
- 現在の状態（例示）:
  - `main` は `upstream/main` より **19 コミット先行 / 0 コミット遅延**
  - 共通祖先（merge-base）は `be4ba47`

現在の先行/遅延はいつでも次で確認できます。

```bash
git rev-list --left-right --count main...upstream/main
# 出力例: 19	0   （左=main の先行数、右=upstream/main の遅延数）
```

---

## 3. 前提チェック

`upstream` リモートが未設定の場合は追加します（設定済みなら不要）。

```bash
git remote add upstream https://github.com/aiming-lab/AutoResearchClaw.git
```

設定状態と追跡関係を確認します。

```bash
git remote -v          # origin と upstream の URL を確認
git branch -vv         # main が origin/main を追跡しているか確認
```

`git remote -v` で `upstream` の **push** 行が表示されていても、そこへ push してはいけません。
**`upstream` は読み取り専用**として扱います。

---

## 4. 標準同期手順（merge 方式）

### Step 0: 作業ツリーをクリーンにする

```bash
git status
```

- clean であることを確認します。未コミットの変更があると merge が失敗したり、
  意図しない変更を巻き込んだりします。
- 変更を一時退避したい場合は `git stash` を使います（後で `git stash pop`）。

### Step 1: 原典の最新を取得する

```bash
git fetch upstream --prune
```

- `--prune` は原典側で削除されたリモート追跡ブランチを整理します。
- この時点ではローカルの `main` は**一切変更されません**。

### Step 2: 取り込む差分を確認する

```bash
git log --oneline main..upstream/main     # 原典側の新規コミット
git diff --stat main upstream/main        # 変更規模
git rev-list --left-right --count main...upstream/main   # 先行/遅延
```

- 1 行目: これから取り込む原典コミットの一覧です。
- 2 行目: どのファイルがどれだけ変わるかの要約です。ここで規模を把握します。
- 3 行目: `main` の先行数と `upstream/main` の遅延数を確認します。

### Step 3: 作業ブランチを作る（任意だが推奨）

```bash
git switch -c sync/upstream-YYYYMMDD
```

- `YYYYMMDD` は実際の日付に置き換えます（例: `sync/upstream-20260920`）。
- `main` を直接触る前に作業ブランチで試すと、問題発生時に安全に切り戻せます。
- なお、**このブランチから `upstream` へ push してはいけません。**

### Step 4: 取り込む（merge）

```bash
git switch main
git merge upstream/main
```

- 線形履歴を残したい場合は `git merge --no-ff upstream/main` を使ってもよいです。
- コンフリクトが出た場合は Step 5 へ進みます。`upstream` は読み取り専用であり、
  merge は `upstream/main` を**取り込むだけ**で原典側には何も書き込みません。

### Step 5: コンフリクトを解消する

- 衝突箇所は第 6 節の**ホットスポット表**を参照して解消します。
- 解消後は次を実行します。

```bash
git add <files>
git merge --continue
```

- 中断して merge 前に戻りたい場合は次を使います（安全に元へ戻ります）。

```bash
git merge --abort
```

- 方針は常に「**原典の改善を活かしつつ、当フォーク固有の追加（docx 既定出力・
  `researchclaw paper`）を再適用する**」です。無関係な整形差分で原典を上書きしないでください。

### Step 6: 検証（必ず実行）

```bash
.venv/bin/python -m pytest -q --ignore=tests/test_anthropic.py
.venv/bin/python -m pytest tests/test_docx_exporter.py tests/test_paper_*.py -q
```

- 原典の変更で**当フォーク固有機能（docx 既定出力 / `researchclaw paper`）が
  壊れていないか**を必ず確認します。
- 注意: 完全なスイートには **4 件の既存失敗**が含まれます。
  - `tests/test_minimax_provider.py` の anthropic プリセット 2 件
  - `tests/test_opencode_bridge.py` の flatten 1 件
  - `tests/test_web_crawler.py` の SSRF 1 件
  - これらは**原典由来**であり、当フォークとは無関係です。前回のフル実行結果は
    **2989 passed, 55 skipped, 4 failed** でした。
- `httpx` が無い環境では `--ignore=tests/test_anthropic.py` を付けて実行します。
- 失敗が上記 4 件のみであることを確認できれば OK です。それ以外の失敗は取り込み起因を疑い、
  原因を切り分けてから push します。

### Step 7: 反映

```bash
git push origin main
```

- 反映先は `origin` のみです。**`upstream` へ push してはいけません**（原典は読み取り専用）。
- force-push は行いません。

### Step 8: 後片付け

```bash
git branch -d sync/upstream-YYYYMMDD
```

- Step 3 で作業ブランチを作った場合のみ実行します（未使用なら不要）。

---

## 5. 自動化スクリプト

上記の手順は `scripts/sync_upstream.sh` に自動化されています。`upstream` は読み取り専用で、
push 先は `origin` のみです。

```bash
./scripts/sync_upstream.sh               # fetch → merge → テスト → origin へ push
./scripts/sync_upstream.sh --dry-run     # 取り込む差分を確認するだけ（変更なし）
./scripts/sync_upstream.sh --no-push     # ローカルで merge まで（push しない）
./scripts/sync_upstream.sh --skip-tests  # テストをスキップ
```

スクリプトは、既知の既存失敗テスト（Step 6 参照）を `--deselect` で除外してから全スイートを
実行します。新しい回帰があればそこで停止し、push しません。作業ツリーに未コミットの追跡対象
変更がある場合は安全のため中断します（未追跡ファイルは無視されます）。

以下は同じ流れを手動で行う場合のコピペ用スクリプトです。`upstream` から取り込み、
テストを実行し、`origin` へ push します。**`git push upstream` は含まれていません。**
`YYYYMMDD` は実行日の日付に置き換えるか、`date` で自動生成してください。

```bash
#!/usr/bin/env bash
# 原典(upstream)から main へ変更を取り込む同期スクリプト
# upstream は読み取り専用。push 先は origin のみ。
set -e

BRANCH="sync/upstream-$(date +%Y%m%d)"

# Step 0: 作業ツリーがクリーンか確認
git status --porcelain
if [ -n "$(git status --porcelain)" ]; then
  echo "未コミットの変更があります。コミットするか git stash してください。" >&2
  exit 1
fi

# Step 1: 原典の最新を取得
git fetch upstream --prune

# Step 2: 取り込む差分を確認
echo "=== upstream 側の新規コミット ==="
git log --oneline main..upstream/main || true
echo "=== 変更規模 ==="
git diff --stat main upstream/main || true
echo "=== 先行/遅延 (main / upstream/main) ==="
git rev-list --left-right --count main...upstream/main

# Step 3: 作業ブランチを作成
git switch -c "$BRANCH"

# Step 4: 取り込み（コンフリクト時は手動解消 -> git add -> git merge --continue）
git merge upstream/main

# Step 6: 検証（既知の失敗 4 件を把握しておくこと）
.venv/bin/python -m pytest -q --ignore=tests/test_anthropic.py
.venv/bin/python -m pytest tests/test_docx_exporter.py tests/test_paper_*.py -q

# Step 7: origin へ反映（upstream へは push しない）
git switch main
git merge "$BRANCH"
git push origin main

# Step 8: 後片付け
git branch -d "$BRANCH"

echo "同期完了。upstream へは push していません。"
```

---

## 6. コンフリクトのホットスポット

当フォークが原典から変更しているファイルです。両者が同じ箇所を触ると衝突します。
原典との差分は全 **37 件**ありますが、特に衝突しやすい代表例を以下に示します。

| ファイル | 当フォークの変更 | 解消方針 |
|---|---|---|
| `researchclaw/config.py` | `ExportConfig.output_format`（既定 `docx`）・`docx_reference`、`ResearchConfig.project_mode`、`EXPORT_FORMATS` / `DEFAULT_EXPORT_FORMAT` / `_normalize_export_format` | 原典の config 変更を活かしつつ、当フォークの追加フィールドを残す |
| `researchclaw/cli.py` | `paper` サブコマンド（`cmd_paper` / パーサ登録 / `main` ディスパッチ） | 双方を統合。原典に新サブコマンドがあれば併存させる |
| `researchclaw/pipeline/stage_impls/_review_publish.py` | Stage 22 の docx 生成ブロックとコンパイルを `output_format` でガード | 原典の export 変更を反映しつつ、docx ガードを再適用 |
| `researchclaw/pipeline/runner.py` | `deliverables/paper.docx` のコピー、docx モードでの再コンパイル回避、manifest 追記 | 原典の packaging 変更に当フォークの追記を統合 |
| `researchclaw/templates/__init__.py` | `markdown_to_docx` / `DocxResult` / `pandoc_available` を再エクスポート | 原典の export 追加と併存 |
| `researchclaw/pipeline/stage_impls/_paper_writing.py` ほか | 当フォークで調整済みのロジック | 原則は原典優先。当フォーク固有の必要分のみ再適用 |

新規追加ファイル（原典に存在しないため通常は衝突しません）:

- `researchclaw/paper/**`
- `researchclaw/templates/docx_exporter.py`
- `tests/test_paper_*.py`
- `tests/test_docx_exporter.py`
- `docs/IMPROVEMENTS.md`

### 解消の一般原則

- **原典の改善を優先して取り込み**、その上に当フォーク固有の追加
  （docx 既定化・paper 専用モード）を**再適用**します。
- 無関係な整形差分で原典を上書きしないでください。
- 迷ったら原典側のロジックを尊重し、当フォークの差分は必要最小限にとどめます。

---

## 7. 代替方式: rebase（非推奨）

- `git rebase upstream/main` はローカル履歴を書き換えます。公開済みの `main` では
  結果を反映するために **force-push が必要**になり、**非推奨**です。
- どうしても直線履歴にしたい場合のみ、専用ブランチで実施し、反映には
  `git push --force-with-lease origin main` を使います（`--force` は使わない）。
- force-push は共同作業者のローカル履歴を壊す可能性があります。実行前に必ず影響を周知してください。
- 通常運用では [4. 標準同期手順（merge 方式）](#4-標準同期手順merge-方式) を推奨します。

---

## 8. 例外ケース

### 原典が force-push / 履歴改変した場合

```bash
git fetch upstream --prune
git log --oneline main..upstream/main
```

- 上記で再確認し、必要なら `upstream/main` の参照を強制的に更新してから merge します。

```bash
git fetch upstream main:refs/remotes/upstream/main --force
git merge upstream/main
```

### 原典の default branch が `main` 以外に変わった場合

- 該当ブランチ名に読み替えてください（以降の `upstream/main` を `upstream/<branch>` に置換）。

### 特定の修正だけ取り込みたい場合

```bash
git fetch upstream
git cherry-pick <sha>   # 原典の SHA を指定
```

### 「取り込まず最新だけ確認したい」場合

```bash
git fetch upstream
```

- `git fetch` のみではローカルの `main` は**変更されません**。差分の確認だけができます。

---

## 9. ロールバック

- merge をやり直す（`git merge` 直後のみ有効）:

```bash
git reset --hard ORIG_HEAD
```

- コンフリクト中で未コミットの状態を中断する:

```bash
git merge --abort
```

- push 済みの場合: 壊れた変更を打ち消す**新しいコミットを積みます**。

```bash
git revert -m 1 <merge_commit>
```

- 公開履歴を書き換える force-push は避けてください。`main` は公開されているため、
  履歴改変は行いません。

---

## 10. 同期チェックリスト

- [ ] 作業ツリーがクリーン
- [ ] `git fetch upstream --prune` を実行
- [ ] `main..upstream/main` の差分を確認
- [ ] `main` へ merge（コンフリクトはホットスポット方針で解消）
- [ ] フルテストを実行（既知の 4 件失敗を把握）
- [ ] docx / paper のフォーカステストがパス
- [ ] `git push origin main`
- [ ] `upstream` へは push していない

---

## 11. CI（継続的テスト）

`.github/workflows/tests.yml` が `main` への push と Pull Request で pytest を実行します
（Python 3.11 / 3.13 のマトリクス）。`pip install -e ".[dev]"` で依存を導入してから
`python -m pytest -q` を走らせます。

Step 6 と同じ既知の既存失敗テストは `--deselect` で除外してあり、CI はグリーンな基準を保ちます。
**それ以外の新しい失敗は CI を赤くする**ため、回帰を検知できます。

さらに、負荷時にタイミング依存で稀に失敗する `tests/test_hitl_advanced.py` の遅延ポーリング
テストを安定させるため、CI は `pytest-rerunfailures` による `--reruns 2 --reruns-delay 1` を
併用します（決定論的な失敗は再試行後も失敗するため、回帰検知は損なわれません）。

`scripts/sync_upstream.sh` の push 前テストはこの CI と同じ除外設定を使っているため、同期後に
ローカルで通過した内容がそのまま CI でも検証されます。

---

## 12. push の独立性（このリポジトリ専用の設定）

本リポジトリは原典から独立して push / 管理できるよう、次のように設定しています。

| 設定 | 値 | 目的 |
|---|---|---|
| `remote.origin.url` | `https://github.com/petadimensionlab/AutoResearchClaw.git` | push 先は自分のリポジトリのみ |
| `remote.upstream.pushurl` | `no_push` | 原典への**誤 push を防止**（fetch 専用） |
| `remote.pushDefault` | `origin` | `git push`（引数なし）は必ず `origin` へ |
| `credential.https://github.com.helper`（ローカル） | petadimensionlab のトークンを返す | `gh auth` のアクティブアカウントに依存せず push 可能 |

これにより、`gh auth` のアクティブアカウントが別アカウント（例: `m-hoikoro`）でも、
本リポジトリへの `git push` は `petadimensionlab` の資格情報で実行されます。

### 新しいクローンで同じ設定を再現する

```bash
git remote add upstream https://github.com/aiming-lab/AutoResearchClaw.git
git remote set-url --push upstream no_push
git config remote.pushDefault origin
git config --local credential."https://github.com".helper ""
git config --local --add credential."https://github.com".helper \
  '!f() { if [ "$1" = get ]; then echo username=petadimensionlab; echo "password=$(gh auth token --user petadimensionlab)"; fi; }; f'
```

- 前提: `gh auth login` で `petadimensionlab` にログイン済みであること（`gh auth status` で確認）。
- 原典は**読み取り専用**です。`git push upstream` は失敗します（意図どおり）。
- ローカルの `.git/config` に保存される設定のため、リポジトリにはコミットされません。
  別マシン・別クローンでは上記コマンドで再設定してください。
