# Jam Finder 東京

都内近郊の「見るだけでなく演奏できる」ジャズ/ブルースセッションを一覧するアプリ。

## 自動で埋まる仕組み
1. `data/venues.json` に会場と開催ルール(例: 第2・4水曜 20:00)を書く
2. GitHub Actions(`.github/workflows/update-jam.yml`)が毎日実行 → `scripts/update.py` が向こう90日分(約3ヶ月)を自動展開し `data/sessions.json` を更新
3. 臨時休業/臨時開催は `overrides` に1行足すだけ
4. 会場サイトに「臨時休業」等の語があると ⚠ を表示

## 公開(GitHub Pages)
1. リポジトリの Settings → Pages → Source を **GitHub Actions** にする
2. このブランチを **デフォルトブランチ(main)にマージ**する(定期実行 `schedule` は main でしか動きません)
3. Actions タブで "Update jam sessions and deploy" を一度手動実行(workflow_dispatch)
以後は毎朝5時(JST)に日程を更新して自動で再公開されます。
ローカル確認: `python3 -m http.server`

## 会場を増やす
- **報告**: アプリ下部のリンク → GitHub Issue フォーム(`.github/ISSUE_TEMPLATE/venue-report.yml`)
- **告知文から下書き**: `python3 scripts/parse_announce.py < announce.txt`(結果は必ず原文と照合)
- **登録**: `python3 scripts/add_venue.py --id ... --rules '[...]'`(検証して sessions.json も再生成)
- 集約サイト(セッションマップ / @jazz)は**無断で取り込まない**方針。`docs/permission-request.md` に許可依頼の文面あり。
- 未確認の候補: `data/candidates.md`

## 注意
登録済みの会場(Bright Brown / Catfish / JazzSpot Intro)は 2026-10-05 時点の公式サイト記載に基づきます。
開催日は変わることがあるため、`venues.json` の `verified` を目安に定期的に公式を確認してください。
会場を足すときは、公式サイトで曜日・時間・参加条件を確認してから `rules` を書きます。

## 自動点検(毎週)
`.github/workflows/watch.yml` が毎週月曜 06:00(JST)に `scripts/watch.py` を実行し、結果を GitHub の Issue「週次チェック: 要確認の会場」にまとめます。
- 登録済みの会場の**公式サイト**を確認(閉店・移転・休業の記載、ジャム/セッションの記載の変化、アクセス不能が続く場合)
- `watch/seeds.txt` に気になる店の公式URLを書くと、開催ルールの下書きを出力
- Instagram・X・Facebook は規約上、自動では読みません。robots.txt を守り、1秒に1リクエスト以内で取得します
- 自動では `venues.json` を書き換えません。人が確認して反映します
ローカル実行: `python3 scripts/watch.py`

## 自動収集パイプライン(MVP)`finder/`
地域×検索語を自動生成 → 検索/Places → 公式サイト巡回 → ルール判定(+AI判定) → SQLite → 網羅率レポート。
```
python3 finder/pipeline.py all            # plan → seed → search → crawl → report
python3 finder/pipeline.py report         # finder/out/report.md と candidates.json
```
- **APIキーなしでも動く範囲**: 検索クエリ生成(約1,700件)、登録済み会場・`watch/seeds.txt` の公式サイト巡回、ルール判定、重複排除、信頼度、状態(NEW/更新/要確認/終了候補)、網羅率
- **キーを環境変数に入れると有効になる範囲**(未検証・キー取得後に動作確認が必要):
  `GOOGLE_CSE_KEY`+`GOOGLE_CSE_CX`(ウェブ検索・無料枠は1日100件)/ `GOOGLE_PLACES_KEY`(店一覧・Place ID)/ `ANTHROPIC_API_KEY`(AI判定)
- SNSは読まず、検索で見つかった場合もURLを控えるだけ。robots.txt順守・1秒間隔・取得件数上限つき
- 地域は `finder/regions.json` を編集して追加(網羅率はこのリストに対する割合)
- 出力はあくまで**候補**。`data/venues.json` への反映は人が確認してから行う

### 週次の自動実行と、APIキーの登録
`.github/workflows/finder.yml` が毎週火曜 07:00(JST)に `finder/pipeline.py all` を実行し、結果を Issue「収集レポート(自動)」に出します。
キーを使うときは、GitHub のリポジトリで **Settings → Secrets and variables → Actions → New repository secret** から、次の名前で登録します(登録した分だけ有効になります)。
`GOOGLE_CSE_KEY` / `GOOGLE_CSE_CX` / `GOOGLE_PLACES_KEY` / `ANTHROPIC_API_KEY`
