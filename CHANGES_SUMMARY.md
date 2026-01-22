# 社内用カスタマイズ変更サマリー

## 変更概要

LINEBOTを社内用に無制限利用できるようカスタマイズしました。

## 主な変更点

### 1. 利用制限の撤廃

**変更ファイル: `services/user_db.py`**
- `get_remaining_count()` メソッドを修正
- 常に999999（無制限）を返すように変更
- 使用回数チェックを実質的に無効化

**変更ファイル: `main.py`**
- 画像受信時の無料枠チェックをコメントアウト
- 使用回数に応じたメッセージ送信を無効化
- ウェルカムメッセージを「無制限でご利用いただけます」に変更
- プロンプト入力画面のメッセージを更新

### 2. Stripe決済機能の削除

**変更ファイル: `main.py`**
- `stripe_service` のインポートをコメントアウト
- `/stripe-webhook` エンドポイントを無効化
- `send_limit_reached_message()` を無効化
- `send_premium_activated_message()` を無効化
- `send_premium_canceled_message()` を無効化

**変更ファイル: `config.py`**
- Stripe関連の環境変数定義をコメントアウト
  - STRIPE_SECRET_KEY
  - STRIPE_PRICE_ID
  - STRIPE_PAYMENT_LINK_ID
  - STRIPE_WEBHOOK_SECRET
- 利用制限関連の環境変数定義をコメントアウト
  - FREE_MONTHLY_LIMIT
  - PREMIUM_MONTHLY_LIMIT

**変更ファイル: `.env`**
- Stripe関連の環境変数をコメントアウト
- 利用制限関連の環境変数をコメントアウト

### 3. デプロイ設定の更新

**変更ファイル: `render.yaml`**
- FREE_MONTHLY_LIMITとPREMIUM_MONTHLY_LIMITを削除
- GOOGLE_SHEETS_IDを追加
- GOOGLE_SERVICE_ACCOUNT_JSONを追加

### 4. ドキュメント追加

**新規ファイル: `DEPLOYMENT_GUIDE.md`**
- 本番環境へのデプロイ手順を記載
- 必要な環境変数の一覧
- Render.comとGoogle Cloud Runの両方の手順
- トラブルシューティング情報

## 残された機能

### 使用統計の記録
- `increment_usage()` は引き続き動作
- Google Sheetsに使用履歴が記録される
- 統計分析やモニタリングに利用可能

### ユーザー管理
- ユーザー情報はGoogle Sheetsで管理
- is_premium、premium_expires_at などのカラムは残存（使用されない）

## 本番デプロイに必要な環境変数

1. **LINE_CHANNEL_SECRET**
2. **LINE_CHANNEL_ACCESS_TOKEN**
3. **KIEAI_API_KEY**
4. **GOOGLE_SHEETS_ID**
5. **GOOGLE_SERVICE_ACCOUNT_JSON**

詳細は `DEPLOYMENT_GUIDE.md` を参照してください。

## テスト結果

- ✅ Pythonファイルの構文チェック完了
- ✅ main.py: コンパイル成功
- ✅ config.py: コンパイル成功
- ✅ services/user_db.py: コンパイル成功

## 新機能: Google Sheetsギャラリー保存

### 追加された機能
**変更ファイル: `services/user_db.py`**
- `Gallery` ワークシートを自動作成
- `save_to_gallery()` メソッドを追加
- 生成画像のメタデータ（作成日時、ユーザーID、タイプ、プロンプト、画像URL、元画像ID）を保存

**変更ファイル: `main.py`**
- 画像生成時に自動でギャラリーに保存
- 各生成画像がLINEに送信されると同時にGoogle Sheetsに記録

### ギャラリーの活用方法
- Google Sheetsの「Gallery」タブで全ての生成画像を確認可能
- ユーザー別、タイプ別の集計が可能
- 人気のあるプロンプトや使用傾向を分析可能
- 画像URLから直接画像にアクセス可能

## Google Cloud Runデプロイ

### 追加されたファイル
**新規ファイル: `deploy.sh`**
- 自動デプロイスクリプト
- Docker イメージのビルド、プッシュ、デプロイを自動化
- 環境変数の検証
- デプロイ後のWebhook URL表示

### デプロイ方法
```bash
cd line_bot
GCP_PROJECT_ID=your-project-id ./deploy.sh
```

オプション:
- `REGION`: デプロイ先リージョン（デフォルト: asia-northeast1）
- `SERVICE_NAME`: サービス名（デフォルト: ishitomo-linebot）

## 次のステップ

1. GCPプロジェクトIDを確認
2. `deploy.sh` を使用してGoogle Cloud Runにデプロイ
3. LINE Developers ConsoleでWebhook URLを設定
4. 実際にLINEで動作テストを実施
5. Google Sheetsの「Gallery」タブで生成画像を確認

## 注意事項

- 社内用のため、すべてのユーザーが無制限で利用可能です
- 決済機能は完全に無効化されています
- KIE.AI APIの利用料金は別途発生します（APIキーの利用状況を確認してください）
