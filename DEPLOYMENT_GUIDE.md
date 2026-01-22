# 本番デプロイガイド（社内用・無制限版）

このLINE Botを本番環境にデプロイする手順です。

## 前提条件

- LINE Developers アカウント
- KIE.AI APIキー
- Google Sheets API認証情報
- Render.com または Google Cloud Run アカウント

## 必要な環境変数

本番環境で以下の環境変数を設定してください：

### 必須の環境変数

1. **LINE_CHANNEL_SECRET**
   - LINE Developers Consoleから取得
   - 現在の値: `16480214ab768b293b03a21e1496bf6e`

2. **LINE_CHANNEL_ACCESS_TOKEN**
   - LINE Developers Consoleから取得
   - 現在の値: `N7Gp9AMhG03YhTqGNQKq...（長いトークン）`

3. **KIEAI_API_KEY**
   - KIE.AI APIキー
   - 現在の値: `e93182223f9c247b808eea4199889ce2`

4. **GOOGLE_SHEETS_ID**
   - Google SheetsのID（URLの `/d/` の後の部分）
   - 現在の値: `1LpmCBMjzsQ7Pe3z8PdyWlFb5iXliVwZoQxtrHGAKUKo`

5. **GOOGLE_SERVICE_ACCOUNT_JSON**
   - Google Service Accountの認証情報（JSON形式の文字列）
   - `config/service-account.json` の内容を1行のJSON文字列として設定
   - 例: `{"type":"service_account","project_id":"...","private_key":"..."}`

## デプロイ方法

### オプション1: Render.com（推奨）

1. Renderアカウントにログイン
2. 「New Web Service」を選択
3. このGitリポジトリを接続
4. `line_bot` ディレクトリをルートディレクトリに設定
5. 環境変数を設定：
   - LINE_CHANNEL_SECRET
   - LINE_CHANNEL_ACCESS_TOKEN
   - KIEAI_API_KEY
   - GOOGLE_SHEETS_ID
   - GOOGLE_SERVICE_ACCOUNT_JSON
6. 「Deploy」をクリック

デプロイ後のWebhook URL: `https://your-app-name.onrender.com/webhook`

### オプション2: Google Cloud Run（推奨）

**自動デプロイスクリプトを使用:**

1. プロジェクトディレクトリに移動：
```bash
cd line_bot
```

2. `.env` ファイルを確認（必須環境変数が設定されていること）

3. デプロイスクリプトを実行：
```bash
GCP_PROJECT_ID=your-project-id ./deploy.sh
```

オプション環境変数:
- `REGION`: デプロイ先リージョン（デフォルト: asia-northeast1）
- `SERVICE_NAME`: サービス名（デフォルト: ishitomo-linebot）

例:
```bash
GCP_PROJECT_ID=my-project REGION=asia-northeast1 SERVICE_NAME=ishitomo-linebot ./deploy.sh
```

**手動デプロイ:**

1. Dockerイメージをビルド：
```bash
cd line_bot
docker build -t gcr.io/YOUR_PROJECT_ID/ishitomo-linebot:latest .
```

2. イメージをプッシュ：
```bash
docker push gcr.io/YOUR_PROJECT_ID/ishitomo-linebot:latest
```

3. Cloud Runにデプロイ：
```bash
# service-account.jsonの内容を1行のJSON文字列に変換
GOOGLE_SERVICE_ACCOUNT_JSON=$(cat ./config/service-account.json | tr -d '\n')

gcloud run deploy ishitomo-linebot \
  --image gcr.io/YOUR_PROJECT_ID/ishitomo-linebot:latest \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars "LINE_CHANNEL_SECRET=${LINE_CHANNEL_SECRET}" \
  --set-env-vars "LINE_CHANNEL_ACCESS_TOKEN=${LINE_CHANNEL_ACCESS_TOKEN}" \
  --set-env-vars "KIEAI_API_KEY=${KIEAI_API_KEY}" \
  --set-env-vars "GOOGLE_SHEETS_ID=${GOOGLE_SHEETS_ID}" \
  --set-env-vars "GOOGLE_SERVICE_ACCOUNT_JSON=${GOOGLE_SERVICE_ACCOUNT_JSON}" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10
```

デプロイ後のWebhook URL: `https://ishitomo-linebot-xxx.a.run.app/webhook`

## LINE Developers設定

1. LINE Developers Console (https://developers.line.biz/) にアクセス
2. チャネル設定 > Messaging API設定
3. Webhook URL を設定：
   - Render: `https://your-app-name.onrender.com/webhook`
   - Cloud Run: `https://linebot-xxx.a.run.app/webhook`
4. Webhookの利用を「オン」に設定
5. 応答メッセージを「オフ」に設定（Botが2重に応答しないため）

## 動作確認

1. LINE公式アカウントを友だち追加
2. ウェルカムメッセージが表示されることを確認
3. 建築パース画像を送信
4. 内観/外観を選択
5. プロンプトを入力
6. 4枚の画像が生成されることを確認

## 注意事項

- **社内用設定**: このボットは無制限利用に設定されています
- **利用制限なし**: 月間の利用回数制限はありません
- **決済機能なし**: Stripe決済機能は無効化されています
- **統計機能**: 使用回数は統計目的でGoogle Sheetsに記録されます
- **ギャラリー機能**: 生成された画像は全てGoogle Sheetsの「Gallery」タブに自動保存されます

## Google Sheetsの構成

デプロイ後、指定したGoogle Sheetsには以下のタブが作成されます：

1. **Users**: ユーザー情報（user_id, created_at, is_premium, premium_expires_at）
2. **Usage**: 使用履歴（user_id, used_at, month）
3. **Gallery**: 生成画像ギャラリー（created_at, user_id, parse_type, custom_prompt, image_url, original_image_id）

Galleryタブには、生成された全ての画像のURLとメタデータが保存され、後から確認・分析が可能です。

## トラブルシューティング

### 画像が生成されない場合

1. ログを確認（Renderの場合は「Logs」タブ）
2. KIEAI_API_KEYが正しく設定されているか確認
3. Google Sheets APIの認証情報が正しいか確認

### Webhookが動作しない場合

1. Webhook URLが正しく設定されているか確認
2. SSL証明書が有効か確認（HTTPSであること）
3. サーバーが起動しているか確認

## サポート

問題が発生した場合は、ログファイルを確認するか、開発者に連絡してください。
