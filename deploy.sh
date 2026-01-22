#!/bin/bash

# Google Cloud Run デプロイスクリプト（社内用LINE Bot）

set -e

# カラー出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Google Cloud Run デプロイ開始${NC}"
echo -e "${GREEN}========================================${NC}"

# 必須環境変数のチェック
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}エラー: GCP_PROJECT_ID が設定されていません${NC}"
    echo "使い方: GCP_PROJECT_ID=your-project-id ./deploy.sh"
    exit 1
fi

# オプション環境変数のデフォルト値
REGION=${REGION:-asia-northeast1}
SERVICE_NAME=${SERVICE_NAME:-ishitomo-linebot}
IMAGE_NAME="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}"

echo -e "${YELLOW}設定確認:${NC}"
echo "  プロジェクトID: $GCP_PROJECT_ID"
echo "  リージョン: $REGION"
echo "  サービス名: $SERVICE_NAME"
echo "  イメージ名: $IMAGE_NAME"
echo ""

# .env ファイルの存在確認
if [ ! -f ".env" ]; then
    echo -e "${RED}エラー: .env ファイルが見つかりません${NC}"
    exit 1
fi

# 環境変数の読み込み
source .env

# 必須環境変数のチェック
REQUIRED_VARS=(
    "LINE_CHANNEL_SECRET"
    "LINE_CHANNEL_ACCESS_TOKEN"
    "KIEAI_API_KEY"
    "GOOGLE_SHEETS_ID"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}エラー: $var が .env に設定されていません${NC}"
        exit 1
    fi
done

echo -e "${GREEN}[1/5] GCP プロジェクトの設定${NC}"
gcloud config set project "$GCP_PROJECT_ID"

echo -e "${GREEN}[2/5] Docker イメージのビルド${NC}"
docker build -t "$IMAGE_NAME:latest" .

echo -e "${GREEN}[3/5] Docker イメージのプッシュ${NC}"
docker push "$IMAGE_NAME:latest"

echo -e "${GREEN}[4/5] Cloud Run へのデプロイ${NC}"

# GOOGLE_SERVICE_ACCOUNT_JSON の準備
if [ -f "./config/service-account.json" ]; then
    GOOGLE_SERVICE_ACCOUNT_JSON=$(cat ./config/service-account.json | tr -d '\n')
else
    echo -e "${RED}エラー: ./config/service-account.json が見つかりません${NC}"
    exit 1
fi

gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME:latest" \
    --platform managed \
    --region "$REGION" \
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

echo -e "${GREEN}[5/5] デプロイ完了！${NC}"

# サービスURLの取得
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}デプロイ成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}サービスURL:${NC} $SERVICE_URL"
echo -e "${YELLOW}Webhook URL:${NC} $SERVICE_URL/webhook"
echo ""
echo -e "${YELLOW}次のステップ:${NC}"
echo "1. LINE Developers Console にアクセス"
echo "2. Webhook URL を設定: $SERVICE_URL/webhook"
echo "3. Webhook の利用を「オン」に設定"
echo "4. 応答メッセージを「オフ」に設定"
echo ""
echo -e "${GREEN}動作確認:${NC}"
echo "LINE公式アカウントを友だち追加して、建築パース画像を送信してください。"
echo ""
