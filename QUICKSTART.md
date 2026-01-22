# クイックスタートガイド

社内用LINE Bot（無制限版）を本番運用するまでの最短手順です。

## 前提条件

- Google Cloud Platform (GCP) アカウント
- Docker がインストール済み
- gcloud CLI がインストール済み
- LINE Developers アカウント
- Google Sheets API 認証情報 (service-account.json)

## ステップ1: 環境変数の確認

`line_bot/.env` ファイルに以下が設定されていることを確認：

```bash
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_access_token
KIEAI_API_KEY=your_kieai_api_key
GOOGLE_SHEETS_ID=your_sheets_id
GOOGLE_SERVICE_ACCOUNT_KEY=./config/service-account.json
```

## ステップ2: Google Cloud Runにデプロイ

```bash
cd line_bot
GCP_PROJECT_ID=your-gcp-project-id ./deploy.sh
```

デプロイが完了すると、Webhook URLが表示されます：
```
Webhook URL: https://ishitomo-linebot-xxx.a.run.app/webhook
```

## ステップ3: LINE Webhookの設定

1. [LINE Developers Console](https://developers.line.biz/) にアクセス
2. チャネル設定 > Messaging API設定
3. **Webhook URL** に表示されたURLを設定
4. **Webhookの利用** を「オン」に設定
5. **応答メッセージ** を「オフ」に設定

## ステップ4: 動作確認

1. LINE公式アカウントを友だち追加
2. ウェルカムメッセージが表示されることを確認
3. 建築パース画像を送信
4. 内観/外観を選択
5. カスタムプロンプトを入力（または「OK」）
6. 4枚の画像が生成されることを確認

## ステップ5: ギャラリーの確認

Google Sheets（GOOGLE_SHEETS_ID で指定したシート）を開く：
- **Gallery** タブに生成画像の情報が保存されています
- 各画像のURL、プロンプト、タイプなどを確認できます

## トラブルシューティング

### デプロイが失敗する場合

```bash
# GCPプロジェクトの確認
gcloud config get-value project

# Dockerが起動しているか確認
docker info

# 認証情報の確認
cat ./config/service-account.json
```

### Webhookが動作しない場合

1. Cloud Runのログを確認：
```bash
gcloud run logs read ishitomo-linebot --region asia-northeast1
```

2. 環境変数が正しく設定されているか確認：
```bash
gcloud run services describe ishitomo-linebot --region asia-northeast1
```

3. LINE Developers ConsoleでWebhook URLが正しく設定されているか確認

### 画像が生成されない場合

- KIEAI_API_KEY が正しく設定されているか確認
- KIE.AI APIの利用制限に達していないか確認
- Cloud Runのログでエラーメッセージを確認

## 便利なコマンド

```bash
# ログのリアルタイム表示
gcloud run logs tail ishitomo-linebot --region asia-northeast1

# サービスの状態確認
gcloud run services list --region asia-northeast1

# サービスの削除（必要な場合）
gcloud run services delete ishitomo-linebot --region asia-northeast1

# 再デプロイ
GCP_PROJECT_ID=your-project-id ./deploy.sh
```

## サポート

詳細な情報は以下を参照してください：
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - 詳細なデプロイ手順
- [CHANGES_SUMMARY.md](./CHANGES_SUMMARY.md) - カスタマイズ内容の詳細

---

## 注意事項

- **無制限利用**: 社内用のため、利用回数制限はありません
- **コスト**: KIE.AI APIの利用料金とGoogle Cloud Runの料金が発生します
- **セキュリティ**: 環境変数に機密情報が含まれるため、適切に管理してください
