# LDR (local-deep-research) 連携 — 引き継ぎ作業計画

> 作成: 2026-09-26 / 対象: AutoResearchClaw ⇄ local-deep-research 連携の実運用化
> 前提: 前セッションで LDR クライアント実装・Consensus 実装・S2 対応は完了済み。本計画は **LDR を実際に起動し、ds4 をバックエンドに動かし、Stage 4 から呼べるようにする** ための引き継ぎ。

---

## 0. ゴール（Definition of Done）

1. LDR サーバが **AirPlay と衝突しない port** で起動している。
2. LDR の LLM バックエンドが **ds4 (`http://100.86.6.79:8000/v1`)** に切り替わっている。
3. `localhost:<port>` に対する **手動スモーク**で研究レポートが返る。
4. AutoResearchClaw の **Stage 4 から `deep_research.md` が生成**され、`artifacts/<run>/` と `deliverables/` に保存される。
5. （任意）フルパイプライン実行で Stage 4 が LDR レポートを取り込むことを確認。

---

## 1. AutoResearchClaw → LDR の呼び出し仕様（確定）

実装: `researchclaw/literature/deep_research_client.py`（`deep_research_report()`、標準ライブラリのみ）
呼び出し元: `researchclaw/pipeline/stage_impls/_literature.py` L683–706

```python
deep_research_report(
    topic,                      # ← Stage 4 の research topic をそのまま query に渡す
    endpoint=_dr.endpoint,      # config.literature_search.deep_research.endpoint
    username=_dr.username,
    password=_dr.password or os.environ.get(_dr.password_env),  # 既定 LDR_PASSWORD
    strategy=_dr.strategy,      # 既定 ""（未指定なら送らない）
    timeout_sec=_dr.timeout_sec # 既定 900
)
```

HTTP フロー（全て本 LDR 版に存在することを実コードで確認済み）:

| # | メソッド | パス | 送信 | 期待レスポンス |
|---|---|---|---|---|
| 1 | GET | `/auth/csrf-token` | — | `{"csrf_token": "..."}` |
| 2 | POST | `/auth/login` | form: `username`, `password`, `csrf_token` / header `X-CSRF-Token` | (username/password 指定時のみ) |
| 3 | POST | `/api/start_research` | JSON `{"query": <topic>, "strategy"?: <str>}` / header `X-CSRF-Token` | `{"research_id": "..."}` |
| 4 | GET | `/api/research/{id}/status` | — | `{"status": "..."}`（completed/failed を判定） |
| 5 | GET | `/api/report/{id}` | — | `{"content": "<markdown>", "summary": "<markdown>", ...}` |

- クライアントは `content` キーを優先して読み取る（`/api/report` の実レスポンスと一致）。
- **失敗は非致命**。どの例外でも `""` を返し Stage 4 は継続。
- 空でなければ保存先: `stage-04/deep_research.md` ＋ `<run_dir>/deep_research.md` ＋ `deliverables/deep_research.md`。

> **重要**: 送信する `query` は **研究トピック文字列そのもの**（例: `"Quantum noise as neural network regularization"`）。LDR 側の検索エンジン（`LDR_SEARCH_TOOL`）と LLM がこの1クエリから調査レポートを生成する。クエリの拡張は LDR 内部で行われる（AutoResearchClaw 側では拡張しない）。

---

## 2. LDR リポジトリの現状（この Mac 上）

- 場所: `/Users/petadimensionlab/workspace/research/local-deep-research`（**ローカルに clone 済み**、`origin`=petadimensionlab フォーク、`upstream`=LearningCircuit）
- HEAD: `0ac1c0587 feat(local): save results under local/result/<ts>, document concurrency fix`
- `.venv` あり（Python 3.13、`local_deep_research` import OK）
- 起動エントリポイント: **`ldr-web`**（`local_deep_research.web.app:main`）。`uv run ldr-web` または `.venv/bin/ldr-web`
- **100.86.6.79 への SSH は不可**（publickey 拒否）。→ LDR は本機で動かし、ds4 を「リモート LLM エンドポイント」として使う構成。

### 2.1 port 設定（要変更）

- 既定 port: `web.port = 5000`（`src/local_deep_research/web/server_config.py:68`）、env `LDR_WEB_PORT`、host 既定 `0.0.0.0`（`LDR_WEB_HOST`）。
- **`localhost:5000` は macOS の AirPlay Receiver が占有**（`Server: AirTunes` を返す）。→ そのままでは LDR に到達できない。
- 対処いずれか:
  - **(推奨) LDR を別 port で起動**: `LDR_WEB_PORT=5055 uv run ldr-web`（以降は `http://localhost:5055`）。
  - もしくはシステム設定 → 一般 → AirDropとHandoff → **AirPlayレシーバを OFF** にして 5000 を空ける。

---

## 3. LDR の LLM バックエンドを ds4 にする（調査結論）

LDR は **`openai_endpoint` プロバイダ**で任意の OpenAI 互換 `base_url` + 任意モデルを指定できる（`langchain_openai.ChatOpenAI` にそのまま渡す）。

### 3.1 設定（`.env` または環境変数）

```bash
LDR_LLM_PROVIDER=openai_endpoint
LDR_LLM_OPENAI_ENDPOINT_URL=http://100.86.6.79:8000/v1
LDR_LLM_MODEL=qwen3.8-flash-next          # 思考あり。chat 変種は qwen3.8-flash-next-chat
LDR_LLM_REQUEST_TIMEOUT=1800
LDR_LLM_MAX_RETRIES=2
LDR_SEARCH_TOOL=pubmed                    # 既存 .env を踏襲（arxiv でも可）
```

- **API キー不要**（`api_key_optional=True`、プレースホルダで動作）。
- `max_tokens` は langchain-openai が `max_completion_tokens` に書き換えて送るが、**ds4 は両方受理することを実測確認済み**（下記 §4）。よって `LDR_LLM_SUPPORTS_MAX_TOKENS` の変更は不要。
- `reasoning_content` は langchain-openai が **無視するだけ**（クラッシュしない）。LDR の `agent_reasoning` UI には出ないが動作に影響なし。思考を UI に出したい場合のみ LDR 側 patch が必要（不要）。
- **注意（egress ポリシー）**: Tailscale `100.x` (CGNAT) は LDR の `is_private_ip` で local 判定されない。`llm.require_local_endpoint=true` にしない／プライマリ検索エンジンを private(library) にしない限りゲートは発動しない（既定 ADAPTIVE + public で OK）。発動する場合は `llm.allowed_local_hostnames` に `100.86.6.79` を追加。

### 3.2 既存 `.env` の扱い（要編集）

現 `.env`（`local-deep-research/.env`）は **Ollama (`gemma4:e4b` @`100.127.45.60`) + pubmed**。ds4 を使うには上記 3.1 の値に変更する。`.env` は **gitignore 済み**（コミットしない）。
バックアップを取ってから編集すること。

---

## 4. ds4 の並列実行の検証（実測済み）

LDR の relevance filter は **多数の並列 LLM 呼び出し** を行う。元 `.env` は Ollama を `OLLAMA_NUM_PARALLEL=8` にして並列対応していた。ds4 は**単一スロット**のため、同等の並列 knob は無い。

**実測結果（本セッション）**: ds4 に **6 並列**リクエストを同時送信 → **全て成功**（各 0.4–1.2s、wall 1.2s）。ds4 は**並列リクエストを拒否せずキューに積んで直列処理**する。

→ **結論（暫定）**: ds4 は LDR の並列フィルタ呼び出しを「拒否せず順番に処理」するため、**クライアント側タイムアウトが十分（`LDR_LLM_REQUEST_TIMEOUT=1800` 既定）なら動作する見込み**。ただし実際の重い並列ワークロード（長いプロンプト＋大量件数）での完走は **§5 で実機検証が必要**。

**追加検証（次セッション推奨）**:
- 現実的な長さのプロンプトで **8–16 並列**を投げ、全件が timeout 内に返るか計測。
- LDR の各 `llm.request_timeout` / `llm.max_retries` が実際に効いているか、ログで確認。
- ds4 側の同時接続上限・スロット待ちの挙動（キュー長で 5s connect timeout に抵触しないか）。

---

## 5. 実行手順（次セッション）

### Step 1 — LDR 設定
1. `local-deep-research/.env` をバックアップし、§3.1 の値へ編集（`LDR_LLM_PROVIDER=openai_endpoint` ほか）。
2. port を 5055 等へ（`LDR_WEB_PORT=5055`）。

### Step 2 — LDR サーバ起動
```bash
cd /Users/petadimensionlab/workspace/research/local-deep-research
LDR_WEB_PORT=5055 uv run ldr-web
# 別ターミナルで疎通確認
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5055/          # 200/302 期待
curl -s http://localhost:5055/auth/csrf-token | head          # {"csrf_token": ...}
```
> `Server: AirTunes` が返るなら port が AirPlay のまま。port を変える。

### Step 3 — 初回ユーザー登録 / ログイン
- LDR は per-user DB（SQLCipher）。Web UI（`http://localhost:5055`）で **初回登録** し、username/password を決める。
- AutoResearchClaw 側の `deep_research.username/password`（または `LDR_PASSWORD` env）に設定。

### Step 4 — LDR スモーク（AutoResearchClaw クライアントで）
```bash
cd /Users/petadimensionlab/workspace/research/AutoResearchClaw
.venv/bin/python - <<'PY'
from researchclaw.literature.deep_research_client import deep_research_report
r = deep_research_report(
    "Quantum noise as neural network regularization",
    endpoint="http://localhost:5055",
    username="<user>", password="<pass>",
    timeout_sec=1800,
)
print(len(r), "chars"); print(r[:500])
PY
```
- まずは LDR 側 `LDR_LLM_PROVIDER` を **軽量確認**で通す（ds4）。長すぎるなら `research_mode`/`strategy` を調整。

### Step 5 — AutoResearchClaw 設定
`config.arc.yaml`（gitignored）の `literature_search.deep_research`:
```yaml
literature_search:
  deep_research:
    enabled: true
    endpoint: "http://localhost:5055"
    username: "<user>"
    password: "<pass>"        # または password_env: "LDR_PASSWORD"
    strategy: ""              # LDR 側既定。必要なら 'quick_research' 等
    timeout_sec: 1800
```

### Step 6 — Stage 4 統合検証
- フル実行（または `--from-stage LITERATURE_COLLECT`）で Stage 4 を走らせ、
  `artifacts/<run>/stage-04/deep_research.md`、`artifacts/<run>/deep_research.md`、`deliverables/deep_research.md` を確認。
- ログに `[deep-research] saved report (N chars)` が出れば成功。

---

## 6. リスク / 未解決点

| # | 項目 | 内容 | 対処 |
|---|---|---|---|
| R1 | port 衝突 | :5000 は AirPlay | LDR を 5055 等へ / AirPlay OFF |
| R2 | ds4 並列 | 単一スロット。並列で詰まる可能性 | §4 の追加検証。`LDR_LLM_REQUEST_TIMEOUT` を十分に |
| R3 | 重い LLM で遅い | LDR は1研究で多数の LLM 呼び出し | 軽量モデル or タイムアウト増。Stage 4 timeout 900→1800 |
| R4 | 認証 | AutoResearchClaw クライアントの login フォーム形が LDR 版と一致するか | Step 4 スモークで確認。不一致なら `deep_research_client.py` の login を修正 |
| R5 | 検索エンジン | PubMed 以外だと `No sources were found` | `LDR_SEARCH_TOOL` を arxiv/wikipedia 等に |
| R6 | レポート形 | `/api/report` は `content` を返す（確認済） | §1 のとおり互換。問題なし |

---

## 7. 参照ファイル

- AutoResearchClaw:
  - `researchclaw/literature/deep_research_client.py`（呼び出し仕様）
  - `researchclaw/pipeline/stage_impls/_literature.py` L683–706（Stage 4 統合）
  - `researchclaw/config.py` `DeepResearchConfig` / `LiteratureSearchConfig`
  - `config.arc.yaml`（gitignored、実設定）
  - `tests/test_deep_research_client.py`
- LDR:
  - `/Users/petadimensionlab/workspace/research/local-deep-research`
  - `.env`（要編集、gitignored）
  - `src/local_deep_research/web/server_config.py`（port 既定 5000）
  - `src/local_deep_research/web/routes/research_routes.py`（`/api/start_research`, `/api/research/<id>/status` L2257, `/api/report/<id>` L2090）
  - `local/README-jp.md`（ユーザーのフォーク運用メモ）

---

## 8. 既に完了していること（再作業不要）

- LDR HTTP クライアント実装 + モックテスト（5）。
- レポートの artifacts/deliverables 保存。
- Consensus バックエンド実装（`sources` からは除外＝未使用、キー削除済み）。
- S2_API_KEY 対応（`s2_api_key` / `S2_API_KEY`、`x-api-key`、レート制限 0.3s）。キー投入のみで有効。
- OpenAlex キー運用、`config.arc.yaml` の LLM 設定（ds4 chat 主 + base レビュー、reasoning_effort）。

---

## 9. 実測検証結果（2026-09-26 実施）

### 9.1 S2_API_KEY — 動作確認 OK ✅

`config.arc.yaml` に `s2_api_key` 設定済み（`llm.s2_api_key` へのフォールバックも可）。
`researchclaw.literature.semantic_scholar.search_semantic_scholar(..., api_key=...)`:

| 条件 | 結果 |
|---|---|
| キーあり | **5件 / 0.9s・実 DOI あり** ✅ |
| キーなし | 0件 / 8.3s（429 で全滅） |

> 補足: キーありでも連続呼び出しで 429 → サーキットブレーカがトリップする事象を確認（S2 のレート制限）。AutoResearchClaw 側のレート制限（キーあり時 0.3s）とブレーカで緩和されるが、短時間に大量クエリを投げないこと。

### 9.2 LDR 実 literature search × ds4 — timeout 検証（in-process `quick_summary`）

条件: LDR クローンの `.venv`、`openai_endpoint`→ds4、`search.tool=pubmed`、同一質問
「What is the prognostic significance of tertiary lymphoid structures in clear cell renal cell carcinoma?」

| モデル | wall time | iterations | sources | summary 長 | Stage4 既定 900s |
|---|---|---|---|---|---|
| **`qwen3.8-flash-next`（base/思考）** | **1411.4s（23.5分）** | 3 | 16 | 5800字 | ❌ 大幅超過 |
| **`qwen3.8-flash-next-chat`（非思考）** | **119.5s（2分）** | 3 | 10 | 4003字 | ✅ 余裕 |

- 実行中、LDR は **ds4 へ 6–8 本の並列接続**を同時確立（relevance filter の並列 LLM 呼び出し）。ds4 は**拒否せずキューに積んで直列処理**（接続は ESTABLISHED のまま待機）。
- **base は思考トークン生成が支配的で、直列化と相まって 23 分** → AutoResearchClaw の Stage 4（既定 900s）では**完走不能**。
- **chat は 2 分**で完走 → 既定 timeout 内に収まる。

### 9.3 chat vs base 品質評価（1 問での比較）

| 観点 | base | chat |
|---|---|---|
| 接地（実 PubMed ソース） | ✅ 16件・実リンク | ✅ 10件・実リンク |
| 引用 `[n]` | ✅ | ✅ |
| 構成 | 段落中心 | **見出し付きで明瞭** |
| 具体性 | 高い（成熟度・空間局在） | 高い（「655例」「peritumoral vs intratumoral」「IRF4」等） |
| 速度 | 23.5分 | **2分（11.8×）** |

**判定**: LDR の用途（検索結果の要約＋引用）では **chat の品質は実用上十分**。base の優位は多段推論の深さだが、本タスクでは speed の損失に見合わない。**→ LDR は chat を推奨**（`.env.ds4` 既定を chat に設定済み）。
> 注意: ソース数・内容は LDR の検索が非決定的なため run 間で変動する（base=16 / chat=10 は同一質問でも検索結果が異なるため）。

### 9.4 認証必須（HTTP 経路）

- LDR サーバを 5055 で起動 → `/auth/csrf-token` = **200**、`web.port` は `LDR_WEB_PORT` で上書き可。
- `POST /api/start_research` は **未認証で 401**。ログイン必須。
- ログインは **form エンコード `username`/`password`（＋`csrf_token`）** を期待 → **AutoResearchClaw クライアントの形式と一致**。
- 既存ユーザー: `Petadimensionlab`（`ldr_auth.db`, id=1, 2026-08-17 作成）。**パスワードは未取得**。
- ダミー認証で実サーバに `deep_research_report()` を実行 → **401 を検知して非致命的に `""` を返す**（Stage 4 を壊さない）ことを確認 ✅。

### 9.5 次セッションへの推奨設定

- `.env.ds4`: `LDR_LLM_MODEL=qwen3.8-flash-next-chat`（設定済み）。起動: `set -a; source .env.ds4; set +a; LDR_WEB_PORT=5055 .venv/bin/ldr-web`。
- `config.arc.yaml` の `literature_search.deep_research`:
  ```yaml
  deep_research:
    enabled: true
    endpoint: "http://localhost:5055"
    username: "Petadimensionlab"
    password: "<ユーザーのLDRパスワード>"   # または password_env: "LDR_PASSWORD"
    timeout_sec: 600        # chat 実測 120s に対し余裕。base 運用時は 1800 でも不足
  ```
- **要ユーザー確認**: LDR のログインパスワード（既存 `Petadimensionlab` アカウント）。不明なら Web UI（`http://localhost:5055`）で新規登録した専用ユーザーを作成する。

---

## 10. HTTP 経路の実測（2026-09-26 追加検証・確定）

### 10.1 クライアントのバグ修正（必須）

**ログインでセッションが再生成される**（session-fixation 対策）ため、**ログイン前に取得した CSRF トークンは無効化**され、`/api/start_research` が `{"error":"The CSRF tokens do not match."}` の **400** を返していた。
→ `researchclaw/literature/deep_research_client.py` を修正し、**ログイン後に `/auth/csrf-token` を再取得**するように変更。修正後は 200 で `research_id` が返る。**この修正は本連携に必須。**

### 10.2 LDR サーバ経路は「ユーザー DB の保存設定」を使う

`ldr-web` の環境変数（`.env.ds4`）は**グローバル既定 / env-lock** に効くが、research 実行時の戦略・エンジン集合は**ログインユーザーの DB 設定**に従う。既定は重い設定だった:

- `search.search_strategy = langgraph-agent`（自律エージェント戦略。**15本の並列 LLM 呼び出し**）
- `search.favorites = [arxiv, searxng, library, openalex]`（**SearXNG は未起動かつ SSRF で遮断** → 無駄な試行）
- S2 API キー未設定 → **429**、arXiv 406 も頻発

### 10.3 timeout 実測（HTTP 経路）

| 戦略 | wall time | report | 判定 |
|---|---|---|---|
| `langgraph-agent`（既定） | **>1503s（25分）でも未完了** | 0 chars | ❌ Stage4 timeout に収まらない |
| **`source-based`（推奨設定）** | **130s** | 12,412字 / 27 sources | ✅ |
| 上記 + 修正済み AutoResearchClaw クライアント | **180.5s** | 11,299字 / 実 PubMed URL | ✅ **end-to-end 成功** |

> ds4 は単一スロット。`langgraph-agent` が 15 本の並列呼び出しを発行 → ds4 が直列化 → 指数的に遅延。`source-based` は呼び出し数が少なく完走可能。

### 10.4 推奨 LDR 設定（設定 API でユーザー DB に保存済み）

`PUT /settings/api/<key>` = `{"value": ...}`（env-lock された設定は 403 で変更不可）:
- `search.search_strategy` = `"source-based"` ← **最重要**
- `search.favorites` = `["pubmed","arxiv","openalex"]`（SearXNG を除外）
- `search.engine.web.semantic_scholar.api_key` = S2 キー（429 緩和）

`config.arc.yaml` の `literature_search.deep_research`（設定済み）:
```yaml
endpoint: "http://localhost:5055"
username: "Petadimensionlab"
password: "<LDRパスワード>"
timeout_sec: 600      # source-based 実測 130–180s に対し余裕
```

### 10.5 結論

- **LDR の HTTP 経路は `source-based` + chat で 3分前後に完走し、AutoResearchClaw Stage 4 の既定 timeout（600–900s）に収まる。**
- `langgraph-agent` は ds4（単一スロット）では実用外（>25分）。
- `search.search_strategy` を `langgraph-agent` に戻すと再び完走不能になるため、**LDR 連携中は `source-based` を維持**すること。

---

## 11. Semantic Scholar レート制限（1 req/s・全エンドポイント累積）

S2 の上限は **1 request/second で、全エンドポイント累積**（`/paper/search`, `/paper/batch` … 合算）。API キーは**上限を引き上げない**（バーストも不可）。

### 11.1 修正内容（`researchclaw/literature/semantic_scholar.py`）

- 旧: `rate_limit = 0.3 if api_key else _RATE_LIMIT_SEC` → キーありで **3.3 req/s**（違反）。
- 新: `_RATE_LIMIT_SEC_KEYED = 1.1`（キーあり）/ `_RATE_LIMIT_SEC = 1.5`（キーなし）。
  - 1.0s ちょうどは秒境界でクリアできるが、実測で 429 が出たため **1.1s のマージン**を採用。
- 単一の `_last_request_time`（`_rate_lock` 保護）を **search と batch で共有** → 全 S2 エンドポイントが同じ 1 req/s バジェットを消費することを保証。
- 実測: 連続 3 呼び出しの開始間隔 ≈1.0s 以上を確認（429 時は指数バックオフ＋回路遮断器で緩和）。

### 11.2 プロセス間の共有バジェットに注意

AutoResearchClaw と **LDR サーバは同一 S2 キー**を使用する。両者は別プロセスなのでレート制限を協調できず、**合算で 1 req/s を超える恐れ**がある。

推奨:
- **S2 の利用は AutoResearchClaw Stage 4 に集約**し、LDR 側では S2 を無効化する（LDR は OpenAlex / arXiv / PubMed で十分）。
- **適用済み**: LDR 設定で以下を設定（ユーザー DB に永続化）:
  - `search.engine.web.semantic_scholar.use_in_auto_search = False`
  - `search.engine.web.semantic_scholar.agent_enabled = False`
  - `search.favorites = [pubmed, arxiv, openalex]`（S2 を入れない）
- AutoResearchClaw 側は `literature_search.inter_query_delay_sec: 1.5`（設定済み）も S2 連打を緩和する。
- ただし env（`.env.ds4`）に S2 キーを残してあるため、将来 LDR で S2 を再有効化する場合は共有バジェットに注意してください。

---

## 12. トピックドメイン別エンジン自動切替 + クエリ改善（2026-09-26 実装）

### 12.1 背景（なぜ必要だったか）

LDR はサーバ既定の `search.tool`（当初 `pubmed`）で検索するため、**生物医学以外のトピックでは無関係な結果しか返さない**。さらに LDR に渡すクエリが生の `topic`（長い疑問文）だと、学術エンジンでは 0 件になりがちだった。

### 12.2 実装した修正

**(A) ドメイン別エンジン自動切替**（`deep_research_client.select_search_engine`）
- `research.domains` を投票方式で評価し LDR エンジンを選択:
  - 生物医学系 → `pubmed`
  - 社会科学/行動/環境/政策系 → `openalex`
  - CS/物理/数学系 → `arxiv`
  - 未一致 → `openalex`（全分野）
- `deep_research.engine` を明示指定すればそれを優先（空なら自動）。
- AutoResearchClaw は `/api/start_research` の `search_engine` フィールドで**per-request 上書き**（LDR 側の env-lock より優先されることを確認済み）。

**(B) LDR クエリを Stage 3 の先頭キーワードクエリに変更**（`_literature.py`）
- 生の `topic` でもなく、複数クエリの `"; "` 結合でもなく、**先頭の1クエリ**を送る。
- 実測: 単一クエリは OpenAlex で十分な件数（例 14,195件）。結合すると激減（同トピックで6件）。

**(C) LDR フォーク修正: OpenAlex の `?`/`*` サニタイズ**（`local-deep-research/src/.../search_engine_openalex.py`）
- OpenAlex は `?`/`*` をワイルドカード扱いし、既定（stemmed）検索で **HTTP 400** → 無音で 0 件化する。
- LDR は戦略内で「?」終わりの質問を生成するため必須。`?`/`*` を空白へ置換して送出。

### 12.3 検証（実トピック end-to-end）

トピック: `"What is the outcome of infectious generosity in promoting nature positive activities?"`（`research.domains` = ML + social + behavioral + environmental）

| 状態 | deep_research.md | 結果 |
|---|---|---|
| 修正前（pubmed） | 無関係（occupational lifestyle diseases） | ❌ |
| 修正前（openalex, 結合クエリ + `?` 400） | 443 B「No sources were found」 | ❌ |
| **修正後（先頭クエリ + openalex + patch）** | **6,644 B・関連内容・実 DOI 12件** | ✅ |

- Stage 4: 280.9s、`deep_research.md` が stage-04 / run_dir / deliverables の 3 か所に生成。
- 引用は Nature / PNAS / PLOS / J.Public Economics 等の実 DOI。

### 12.4 クエリ緩和（0件フォールバック）— 実装済み

OpenAlex エンジン（LDR フォーク）に **0件時のクエリ緩和リトライ**を追加した:
- `0件` のとき、質問から括弧・年号・引用符・記号・ストップワードを除去し内容語のみ（最大8語）に簡略化して**もう一度検索**する。
- 実装: `_simplify_openalex_query()` と `_get_previews` のリトライ（`?`/`*` サニタイズと併用）。

実測（実トピック Stage 4、いずれも LDR 経由）:

| 指標 | 緩和前 | **緩和後** |
|---|---|---|
| 0件で終わった検索 | 2/4 | **0/4** |
| 生成質問のヒット | 2/4 | **4/4**（3件は緩和で回復: 65 / 3,786 / 233件） |
| `deep_research.md` | 6,644 B / 12 DOI | **11,415 B / 28 DOI** |

→ 生成される超具体的な「?」質問も、緩和により OpenAlex でヒットするようになった。

残る制約:
- それでも LDR の生成質問は超具体的で、緩和に依存している。根本強化には **汎用 Web 検索エンジン（Tavily / Brave / Exa 等）の API キー**を LDR に設定するのが最も効果的（未設定）。
- 検証用 LDR サーバ（5055）は停止済み。

---

## 13. LDR リンクの取り込み（A）と Stage 1–3 での活用（B）（2026-09-26 実装）

### 13.1 背景

従来 `deep_research.md` は **保存されるだけ**で、どのステージも読んでおらず、LDR の引用リンクは `candidates.jsonl` / `references.bib` に**入っていなかった**（実測: レポートの 28 DOI のうち candidates にあるのは 8 件のみで、それも他ソースが偶然見つけた同一論文）。

### 13.2 A: LDR 引用をコーパスへ取り込み

- `deep_research_client.parse_report_sources()`: レポートの `## Sources` ブロック（`[N] Title …` ＋ `URL:` 行）を解析し、DOI/URL ごとに `Paper(source="ldr")` を返す（DOI 優先で重複排除）。
- Stage 4: LDR レポート取得を **`candidates.jsonl` / `references.bib` の書き出し前**に移動し、パースした論文を **DOI 重複排除のうえ `candidates` と `bibtex_entries` にマージ**。→ Stage 5 スクリーニング・Stage 7 合成・Stage 23 引用検証まで流れる。

**実測（実トピック Stage 4）**: `source="ldr"` の候補がマージされ、**LDR DOI 7/8 が candidates.jsonl と references.bib の両方に出現**。

### 13.3 B: Stage 1–3 での活用（pre-search）

- Stage 3（SEARCH_STRATEGY）で、クエリ生成の**前に LDR を実行**し、レポートを `run_dir/deep_research.md` にキャッシュ。
- Stage 3 の `search_strategy` プロンプトに `{deep_research}` プレースホルダを追加（`prompts/ml.py`, `prompts/hep.py`）し、**LDR の知見をクエリ生成の背景として注入**（空時は `(none available)`）。
- Stage 4 はキャッシュ (`run_dir/deep_research.md`) を**再利用**するため、LDR 呼び出しは 1 run につき Stage 3 の 1 回のみ。

**実測**: Stage 3 の所要が **20s → 121s**（LDR 実行）、run_dir レポートの mtime が Stage 3 時点、stage-04 が Stage 4 時点 → pre-search + 再利用を確認。`{deep_research}` は正しく置換される。

### 13.4 補足（レポート規模の変動）

LDR のレポートは **同一クエリでも実行間で大きく変動**する（keyword クエリで 12 DOI / 28 DOI を観測）。したがって DOI 数の差はクエリ形式より **LDR の非決定性**に起因する。pre-search が topic を使うことは品質上の問題ではない。

### 13.5 追加された主なコード

- `researchclaw/literature/deep_research_client.py`: `parse_report_sources()`（＋テスト 2 件）。
- `researchclaw/pipeline/stage_impls/_literature.py`: `_run_ldr_deep_research()` / `_cached_ldr_report()`、Stage 3 pre-search + 注入、Stage 4 マージ。
- `researchclaw/prompts/ml.py` / `hep.py`: `{deep_research}` プレースホルダ。

---

## 14. 最終成果物への Appendix 追加（C）（2026-09-26 実装）

### 14.1 内容

最終論文に **Appendix セクション「Local Deep Research Results」** を追加し、LDR の結果を透明性のために同梱する。

- 実装: `_review_publish._build_ldr_appendix()`（`run_dir/deep_research.md` を読み `# Appendix: Local Deep Research Results` で包む）。
- Stage 22（EXPORT_PUBLISH）で、`paper_final` / `final_paper_latex` に appendix を追記してから `.tex` / `.docx` を生成。
- 設定: `export.include_deep_research_appendix`（既定 `true`）。`false` で無効化。レポートが無い場合は何もしない。

### 14.2 反映先（検証済み）

Stage 22 を実行して確認（`paper_revised.md` を与えて export のみ実行）:

| ファイル | Appendix |
|---|---|
| `stage-22/paper_final.md` | ✅ |
| `stage-22/paper_final_latex.md` | ✅ |
| `stage-22/paper.tex`（`\section{Appendix: Local Deep Research Results}`） | ✅ |
| `stage-22/paper.docx` | ✅ |
| `deliverables/paper_final.md` | ✅ |

### 14.3 追加されたコード／テスト

- `researchclaw/config.py`: `ExportConfig.include_deep_research_appendix`（＋パーサ）。
- `researchclaw/pipeline/stage_impls/_review_publish.py`: `_build_ldr_appendix()`、Stage 22 での追記。
- `config.researchclaw.example.yaml`: 設定例と説明。
- `tests/test_ldr_appendix.py`: 4 件。

> 注: `_review_publish.py` の既存の型エラー（`_execute_citation_verify` の `dict[str, float]`）は本変更とは無関係（HEAD 時点で存在）。
