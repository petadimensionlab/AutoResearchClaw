# AutoResearchClaw 改善レポート: 論文専用モードと Word (.docx) 既定出力

本ドキュメントは、AutoResearchClaw に対する 2 つの改善をまとめたものです。既存の 23 ステージ
パイプラインを再利用しつつ、論文構築だけを独立実行する導線と、既定エクスポート形式の変更を
追加しています。記載内容は検証済みの事実のみで、未実装の機能は含みません。

---

## 1. 背景 / 目的

AutoResearchClaw は 23 ステージの自律研究パイプラインです。文献検索から実験、そして論文
構築までを一気通貫で実行します。実運用では「実験は既に終わっていて、手元に markdown の
分析レポートがある。あとは論文だけを組み立てたい」というケースが頻出します。また、生成物の
受け渡し先では LaTeX より Word (.docx) が好まれる場面が多くあります。

今回の改善は以下の 2 点です。

1. **論文構築のみを独立実行できるサブモジュール**を追加（既に用意した markdown 分析結果
   レポートから、Stage 16-23 のみを実行）。
2. **既定の出力を LaTeX から Word (.docx) に変更**（markdown から pandoc で docx を生成。
   LaTeX は選択式として維持）。

どちらも既存実装を再利用し、論文執筆やレビューのロジックを再実装していません。

---

## 2. 改善 A: 論文専用サブモジュール `researchclaw/paper/`

### 2.1 パッケージ構成

```
researchclaw/paper/
├── __init__.py      # 公開 API の再エクスポート
├── report.py        # markdown 分析レポートの寛容パーサ
├── seed.py          # run ディレクトリへの成果物シード
└── builder.py       # Stage 16-23 の実行オーケストレーション
```

### 2.2 各モジュールの役割

#### `researchclaw/paper/report.py`

- 公開シンボル: `AnalysisReport`, `load_analysis_report(path)`
- markdown レポートを寛容に解析します。
  - タイトル (`# ...`)
  - `## Abstract`
  - `##` / `###` セクション
  - `Keywords:`
  - パイプ表メトリクス（1 列目ラベル + 数値列）
  - 全数値トークン
  - フェンス付き ` ```bibtex ` ブロック
- 欠損は空値に劣化させ、例外は出しません。ただし存在しないパスは `FileNotFoundError` を
  送出します。

#### `researchclaw/paper/seed.py`

- 公開シンボル: `SeedResult`, `seed_run_dir(...)`
- run ディレクトリへ以下の成果物を書き出します。
  - `stage-01/goal.md`
  - `stage-07/synthesis.md`
  - `stage-08/hypotheses.md`
  - `stage-14/analysis.md`
  - `analysis_best.md`
  - `stage-15/decision.md`（`PROCEED` を含む）
  - `stage-14/experiment_summary.json` と `experiment_summary_best.json`
    （非空の `condition_summaries` / `metrics_summary` / `best_run.metrics`、および
    レポート内数値を接地する `_report_values`）
  - `stage-04/references.bib`（任意）
  - `stage-14/charts/`（任意）

#### `researchclaw/paper/builder.py`

- 公開シンボル: `PaperBuildResult`, `build_paper_from_report(...)`
- config を解決し、`research.project_mode="docs-first"` を強制します。
- `execute_pipeline(from_stage=Stage.PAPER_OUTLINE, to_stage=Stage.CITATION_VERIFY, auto_approve_gates=True)`
  を呼び出します。
- **重要**: 既存の Stage 16-23 実装を再利用しています。論文執筆・レビュー・改訂・品質ゲート・
  アーカイブ・エクスポート・引用検証を再実装していません。

### 2.3 なぜ seed が必要か

ステージはオブジェクトではなく、`run_dir/stage-NN/*` の成果物をディスクから読みます。そのため
論文専用モードでは、後続ステージが期待するファイルを事前に配置する必要があります。

- Stage 16 の契約は `analysis.md` と `decision.md` の存在を要求します。
- Stage 20 は `VerifiedRegistry` が空かつ実験失敗時のみブロックします。したがって
  非空の `experiment_summary.json` が必須です。
- `_collect_real_metric_values` が接地値を集めるため、レポート内の数値がサニタイズで
  消えません。

これらを満たすため、`seed_run_dir(...)` が run ディレクトリへ成果物一式を書き出します。

### 2.4 使用方法

#### CLI

```bash
researchclaw paper --report <analysis_report.md> [--output <run_dir>] [--config <config.yaml>] \
    [--topic "<topic>"] [--authors "A. Author"] [--output-format docx|latex|both] \
    [--charts <dir>] [--references <references.bib>] [--run-id <id>]
```

#### Python API

```python
from researchclaw.paper import build_paper_from_report

result = build_paper_from_report("analysis_report.md", "artifacts/my-paper", output_format="docx")
print(result.paper_docx, result.ok)
```

#### 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `--report <analysis_report.md>` | 必須 | 根拠となる markdown 分析レポートのパス |
| `--output <run_dir>` | 任意 | 出力先 run ディレクトリ |
| `--config <config.yaml>` | 任意 | 使用する設定ファイル |
| `--topic "<topic>"` | 任意 | 論文のトピック |
| `--authors "A. Author"` | 任意 | 著者名 |
| `--output-format docx\|latex\|both` | 任意 | この run の出力形式。`export.output_format` を上書き |
| `--charts <dir>` | 任意 | 図表ディレクトリ |
| `--references <references.bib>` | 任意 | BibTeX ファイル |
| `--run-id <id>` | 任意 | run の識別子 |

### 2.5 実行されるステージ一覧

| Stage | 名前 | 役割 |
|-------|------|------|
| 16 | `PAPER_OUTLINE` | 論文アウトライン生成 |
| 17 | `PAPER_DRAFT` | セクション単位のドラフト執筆 |
| 18 | `PEER_REVIEW` | 多エージェント査読（根拠整合チェック付き） |
| 19 | `PAPER_REVISION` | 指摘に基づく改訂 |
| 20 | `QUALITY_GATE` | 品質ゲート |
| 21 | `KNOWLEDGE_ARCHIVE` | ナレッジのアーカイブ |
| 22 | `EXPORT_PUBLISH` | エクスポート（docx / tex / bib） |
| 23 | `CITATION_VERIFY` | 引用検証 |

---

## 3. 改善 B: 既定の Word (.docx) 出力

### 3.1 新規 `researchclaw/templates/docx_exporter.py`

- 公開シンボル:
  - `DocxResult`
  - `pandoc_available()`
  - `markdown_to_docx(markdown, out_path, *, title, authors, bib_path, reference_doc, timeout=120)`
- バックエンドは pandoc です。
- pandoc 不在時は例外を投げず、`success=False, pandoc_available=False` を返します
  （graceful degradation）。

### 3.2 前処理の変換規則

pandoc が落とす構文を事前に変換します。

| 入力 | 変換後 | 条件 |
|------|--------|------|
| `\begin{table}` / `tabular` | パイプ表 | `\caption` は太字キャプション行 |
| `\cite{a,b}` | `[@a; @b]` | bib がある場合（`--citeproc`） |
| `\cite{a,b}` | `[a; b]` | bib がない場合 |
| `\[..\]` | `$$..$$` | 常時 |
| `\hline` / `\toprule` / `\midrule` / `\bottomrule` / `\label` | 除去 | 常時 |
| `\_` | `_` | アンダースコアの復元 |

### 3.3 設定

```yaml
export:
  output_format: "docx"        # docx (既定) | latex | both
  docx_reference: ""           # 任意: pandoc 参照 .docx
```

- `export.output_format`: `"docx"` が既定。`"latex"` または `"both"` も選択可能。
- `export.docx_reference`: 任意の pandoc 参照 docx（Word スタイル調整用）。
- `research.project_mode`: `"docs-first"` を指定すると「全て simulated」「実メトリクス無し」の
  ハードブロックを回避します。既定は空文字で後方互換です。

### 3.4 Stage 22 の挙動

`paper_final.md`・`paper.tex`・`references.bib` は常に生成されます。

| `export.output_format` | `paper.docx` | PDF コンパイル |
|------------------------|--------------|----------------|
| `docx`（既定） | 生成 | スキップ（pdflatex を実行しない） |
| `latex` | 生成しない | 従来通り PDF を生成 |
| `both` | 生成 | 従来通り PDF を生成 |

### 3.5 deliverables と後方互換

- `deliverables/paper.docx` を追加し、manifest と notes に記載します。
- `docx` モードでは 2 回目のコンパイルをスキップします。
- `docx` モードで `paper.pdf` が存在しなくてもエラーではありません。
- 既定変更の影響と後方互換:
  - `--output-format latex` または `both` で PDF を復帰できます。
  - Overleaf 用の `paper.tex` は常に生成されます。

`docx` モードで既定生成される成果物:

```
deliverables/{paper_final.md, paper.docx, paper.tex, references.bib, verification_report.json}
```

`paper.pdf` は `latex` / `both` のときのみ生成されます。

---

## 4. 設定リファレンス（該当抜粋）

```yaml
research:
  project_mode: "docs-first"   # 任意: 実験なしレポート根拠の論文でアンチファブリケーションのハードブロックを回避

export:
  target_conference: "neurips_2025"
  authors: "Anonymous"
  bib_file: "references"
  output_format: "docx"        # docx | latex | both  (既定: docx)
  docx_reference: ""           # 任意: pandoc 参照 .docx
```

---

## 5. 検証エビデンス

### 新規テスト

| テストファイル | 内容 |
|----------------|------|
| `tests/test_docx_exporter.py` | docx エクスポータ（10 件） |
| `tests/test_paper_report.py` | レポートパーサ |
| `tests/test_paper_seed.py` | run ディレクトリのシード |
| `tests/test_paper_builder.py` | 論文ビルダー |
| `tests/test_paper_cli.py` | CLI |

### スイート結果

- 関連スイート: **353 passed**
- 全体: **2989 passed, 55 skipped**

### 既知の失敗について

既知の失敗 4 件は、クリーンな HEAD worktree でも同一に失敗する**既存**不具合です
（`httpx` 未導入 / opencode bridge / SSRF の NAT64 DNS）。本変更とは無関係です。

### オフライン統合スモーク結果

- 実ヘルパ `_read_best_analysis`・`_read_prior_artifact` が seed 成果物を解決。
- `VerifiedRegistry` n=20（非空）。
- `_exp_failed=False`。
- 生成 docx に表の値と引用が保持。
- `ruff` の新規指摘ゼロ、`py_compile` OK。

課金 API は不使用です（テストは全てオフライン / モック）。

---

## 6. 変更ファイル一覧

### 新規

| ファイル | 内容 |
|----------|------|
| `researchclaw/paper/__init__.py` | 公開 API の再エクスポート |
| `researchclaw/paper/report.py` | `AnalysisReport` / `load_analysis_report` |
| `researchclaw/paper/seed.py` | `SeedResult` / `seed_run_dir` |
| `researchclaw/paper/builder.py` | `PaperBuildResult` / `build_paper_from_report` |
| `researchclaw/templates/docx_exporter.py` | `DocxResult` / `pandoc_available` / `markdown_to_docx` |
| `tests/test_docx_exporter.py` | docx エクスポータのテスト |
| `tests/test_paper_report.py` | レポートパーサのテスト |
| `tests/test_paper_seed.py` | シードのテスト |
| `tests/test_paper_builder.py` | ビルダーのテスト |
| `tests/test_paper_cli.py` | CLI のテスト |
| `docs/IMPROVEMENTS.md` | 本ドキュメント |

### 変更

| ファイル | 内容 |
|----------|------|
| `researchclaw/config.py` | `export.output_format` / `export.docx_reference` / `research.project_mode` |
| `researchclaw/cli.py` | `researchclaw paper` サブコマンド |
| `researchclaw/templates/__init__.py` | docx エクスポータの再エクスポート |
| `researchclaw/pipeline/stage_impls/_review_publish.py` | Stage 22 の docx / latex / both 分岐 |
| `researchclaw/pipeline/runner.py` | 論文専用モードの起点・終点制御 |
| `README.md` | Paper-Only Mode と docx 既定出力の記載 |
| `docs/integration-guide.md` | 統合ガイドの追記 |
| `.claude/skills/researchclaw/SKILL.md` | スキルの追記 |
| `config.researchclaw.example.yaml` | 設定例の追記 |

---

## 7. 前提 / 既知の制約

- docx 生成には `pandoc` が必要です。無い場合は警告のみで継続します。
- 論文専用モードは LLM 設定（`llm.*`）が必要です。
- レポート内の数値は接地値として登録されます（サニタイズで消えません）。
