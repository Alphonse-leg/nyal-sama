# 大預言猫ニャル様 — GitHub / Render 配置版

## 内容
- Flask アプリ（`app.py` から起動）
- Render 用 `render.yaml` / `Procfile`
- スマホホーム画面用アイコンと PWA manifest
- ブラウザセッションごとにプロフィール・会話・予言データを分離

## GitHub に登録
1. この ZIP を展開します。
2. GitHub で新しい **Private repository** を作成します（最初は非公開を推奨）。
3. ZIP 内のファイルをアップロードして main ブランチへ登録します。
4. `.env` や API キー、個人データベースは ZIP に含めていません。API キーをソースコードに書かないでください。

## Render で公開
1. Render にログインし、New → Blueprint を選びます。
2. GitHub リポジトリを接続し、`render.yaml` を使って作成します。
3. Render の Environment で `GEMINI_API_KEY` に Gemini API キーを設定します。`NYALSAMA_SECRET_KEY` は生成値を使います。
4. デプロイ完了後、表示された URL を開いて動作を確認します。

## スマホのホーム画面に追加
- Android / Chrome: 公開 URL を開き、ブラウザメニューから「ホーム画面に追加」または「アプリをインストール」。
- iPhone / Safari: 公開 URL を開き、共有メニュー →「ホーム画面に追加」。

## 大切な注意
- Gemini API の利用には API キーが必要です。無料枠・モデル名・利用上限は Google 側の条件で変わります。
- この構成は Render Free の一時ファイルシステムで動きます。再デプロイや再起動などで SQLite の利用データが失われる可能性があります。長期保存するには永続ストレージまたは外部データベースが必要です。
- ブラウザ単位でデータを分けていますが、Cookie を消すと別ユーザー扱いになり、以前の記憶や会話へ戻れなくなることがあります。現状はアカウント登録・パスワード保護・データのバックアップ機能がありません。大勢に本格公開する前に、利用規約・プライバシー説明・データ永続化・バックアップを追加することをおすすめします。
- 予言は娯楽用です。医療・金銭などの重要な判断には使わないでください。

## ローカル起動
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# GEMINI_API_KEY を環境変数に設定
python app.py
```
