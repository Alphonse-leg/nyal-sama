# 大預言猫ニャル様

## GitHub / Render 公開用

このZIPは、作者情報と「アプリについて」ページを追加した公開用ファイルです。

- 「アプリについて」メニューを追加
- 著作制作：小澤保則
- mail: yasunoriozawa@gmail.com
- Render起動コマンド：`gunicorn app:app`

## GitHubにアップロードするファイル
ZIPファイルそのものではなく、ZIPを展開した中身をリポジトリの一番上（root）にアップロードしてください。
`app.py`、`requirements.txt`、`render.yaml`、`.gitignore`、`.env.example`、`static/`、`templates/` が対象です。

**`.env` と `nyalsama.db` は含めていません。APIキーや個人の会話履歴をGitHubへ公開しないためです。** `.env.example` はサンプルなので実際のAPIキーは入れず、Renderの Environment に `GEMINI_API_KEY` を登録してください。

既存リポジトリにアップロードするときは、先に現在の状態をバックアップしてください。`app.py` と `templates/` の既存ファイルを更新するため、現在の公開版と内容が入れ替わる場合があります。アップロード後、RenderのLogsでデプロイ完了を確認してください。
