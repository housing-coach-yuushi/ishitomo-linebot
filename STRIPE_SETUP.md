# Stripe決済セットアップガイド

## 概要
このLINEボットは、Stripeを使用して月額サブスクリプション（1,980円/月）の決済を処理します。

## セットアップ手順

### 1. Stripeアカウント作成
1. https://dashboard.stripe.com/register にアクセス
2. アカウントを作成
3. 日本のビジネス情報を登録

### 2. 商品とPriceの作成

#### ダッシュボードで作成する場合:
1. Stripe Dashboard → **商品** → **商品を追加**
2. 商品情報を入力:
   - 名前: `AIパース作成くん プレミアムプラン`
   - 説明: `月額1,980円で毎月20回までAIパースを生成できるプレミアムプラン`
3. 価格を設定:
   - 請求モデル: **定期課金**
   - 価格: **¥1,980**
   - 請求期間: **月次**
4. 作成後、**Price ID** (`price_xxxxx`) をコピー

### 3. Payment Linkの作成（推奨）

Payment Linkを使うと、簡単に決済リンクを生成できます:

1. Stripe Dashboard → **Payment Links** → **新規作成**
2. 商品を選択: 先ほど作成した `AIパース無制限プラン`
3. 設定:
   - 支払い方法: クレジットカード
   - 顧客情報収集: メールアドレス（オプション）
4. 作成後、URLから **Payment Link ID** を取得
   - URL例: `https://buy.stripe.com/test_xxxxx`
   - `test_xxxxx` の部分がPayment Link ID

### 4. Webhook設定

LINEボットがStripeの支払い完了イベントを受け取るために、Webhookを設定します:

1. Stripe Dashboard → **開発者** → **Webhook**
2. **エンドポイントを追加**をクリック
3. エンドポイントURL: `https://your-render-url.onrender.com/stripe-webhook`
   - 例: `https://ai-parse-line-bot.onrender.com/stripe-webhook`
4. 監視するイベントを選択:
   - `checkout.session.completed` - 新規サブスクリプション
   - `invoice.payment_succeeded` - サブスクリプション更新
   - `customer.subscription.deleted` - サブスクリプションキャンセル
5. 作成後、**署名シークレット** (`whsec_xxxxx`) をコピー

### 5. 環境変数の設定

#### Renderダッシュボードで設定:
1. Render Dashboard → サービス選択 → **Environment**
2. 以下の環境変数を追加:

```
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_PRICE_ID=price_xxxxx
STRIPE_PAYMENT_LINK_ID=xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

#### ローカル開発用(.env):
```bash
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_PRICE_ID=price_xxxxx
STRIPE_PAYMENT_LINK_ID=xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

### 6. テスト

#### テストモードでの動作確認:
1. LINEボットで画像を3回送信して無料枠を使い切る
2. 4回目に決済リンクが表示されることを確認
3. テストカード番号 `4242 4242 4242 4242` で決済
4. プレミアム有効化メッセージが届くことを確認
5. 無制限に画像生成できることを確認

#### テストカード情報:
- カード番号: `4242 4242 4242 4242`
- 有効期限: 任意の未来の日付（例: `12/34`）
- CVC: 任意の3桁（例: `123`）
- 郵便番号: 任意

### 7. 本番環境への移行

テストが完了したら、本番環境に切り替えます:

1. Stripe Dashboard → 右上の **テストモード** をオフにする
2. 本番用の商品とPriceを作成（手順2を再実行）
3. 本番用のWebhookを設定（手順4を再実行）
4. 環境変数を本番キーに更新:
   - `sk_test_xxxxx` → `sk_live_xxxxx`
   - `price_xxxxx` → `price_xxxxx`（本番用）
   - `whsec_xxxxx` → `whsec_xxxxx`（本番用）

## 料金体系

### 無料プラン
- 月3回まで無料
- 1回あたり4枚の画像生成

### プレミアムプラン（月額1,980円）
- 月20回まで生成可能（1回4枚 = 合計80枚/月）
- 1回あたり約99円（通常1回約60円のコスト）
- 毎月1日に回数リセット
- 自動更新（キャンセル可能）

**コスト計算:**
- API費用: 1回あたり約60円
- プレミアム単価: 1,980円 ÷ 20回 = 99円/回
- 利益: 約39円/回

## サブスクリプション管理

### ユーザーがキャンセルしたい場合:
1. Stripe Customer Portalを使用（別途設定が必要）
2. または、手動でStripe Dashboardから解約

### 管理者が確認する場合:
1. Stripe Dashboard → **顧客**
2. ユーザーのメールアドレスまたはLINE IDで検索
3. サブスクリプション状態を確認

## トラブルシューティング

### Webhookが動作しない場合:
1. Render のログを確認: `=== Stripe Webhook received ===` が表示されるか
2. Stripe Dashboard → Webhook → ログを確認
3. エンドポイントURLが正しいか確認
4. Webhook署名シークレットが正しいか確認

### 決済が完了してもプレミアムにならない場合:
1. Renderのログで `Premium activated for user: xxx` を確認
2. データベースを確認: `SELECT * FROM users WHERE user_id = 'xxx';`
3. Webhook設定で `checkout.session.completed` が有効か確認

## 参考リンク

- [Stripe Documentation](https://stripe.com/docs)
- [Stripe Subscriptions](https://stripe.com/docs/billing/subscriptions/overview)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Testing](https://stripe.com/docs/testing)
