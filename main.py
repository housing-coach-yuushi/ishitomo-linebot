"""
LINE Bot for AI Architectural Rendering
住宅営業マン向けAIパース生成LINEボット
"""
import os
import sys
import httpx
import hmac
import hashlib
import base64
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from linebot.v3.messaging import (
    Configuration,
    AsyncApiClient,
    AsyncMessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
)
from linebot.v3.exceptions import InvalidSignatureError

from config import settings
from services.kie_api import generate_parse_multi
from services.user_db import UserDB
from services.stripe_service import stripe_service

def log(message: str):
    """ログ出力（標準出力を即座にフラッシュ）"""
    print(message, flush=True)
    sys.stdout.flush()


app = FastAPI(title="AI Parse LINE Bot")

# 起動時ログ
log("=" * 50)
log("AI Parse LINE Bot Starting...")
log(f"Python version: {sys.version}")
log(f"/data exists: {os.path.exists('/data')}")
if os.path.exists('/data'):
    log(f"/data writable: {os.access('/data', os.W_OK)}")
log("=" * 50)

# LINE Bot設定
configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)

# ユーザーDB
user_db = UserDB()

# ユーザーの状態管理（メモリ上、本番はRedis推奨）
user_states = {}

# Exterior Base Prompt
EXTERIOR_BASE_PROMPT = """Transform this architectural render into a photorealistic exterior image.
DO NOT change the building shape, composition, angle, depth, camera position, or perspective lines.
Only enhance materials, textures, and lighting to look like a real photograph.

【STRICT REQUIREMENTS】
- Do not alter the exterior shape at all
- Keep window positions, wall lines, roof shape, and shadow directions exactly the same
- Maintain the same wide-angle ratio
- Preserve the aspect ratio (e.g., 3:4, landscape)
- Do not change the background composition

【PHOTOREALISTIC CONDITIONS】
- Exterior walls: ceramic siding texture
- Road: asphalt texture
- Background: residential neighborhood
- Concrete reflection: none
- Window glass reflection: yes
- Weather: sunny
- People: none
{custom_prompt}

【IMPORTANT】
Do not interpret or change the building's shape or proportions.
Keep the original contour lines and structure intact, only enhance textures to high-quality photorealistic finish."""

# Interior Base Prompt
INTERIOR_BASE_PROMPT = """Transform this architectural interior render into a photorealistic interior image.
DO NOT change the room shape, composition, angle, depth, camera position, or perspective lines.
Only enhance materials, textures, and lighting to look like a real photograph.

【STRICT REQUIREMENTS】
- Do not alter the room shape at all
- Keep window positions, wall lines, ceiling shape, and shadow directions exactly the same
- Maintain the same wide-angle ratio
- Preserve the aspect ratio (e.g., 3:4, landscape)
- Do not change furniture or equipment placement

【PHOTOREALISTIC CONDITIONS】
- Floor: hardwood flooring texture
- Walls: white wallpaper texture
- Ceiling: white wallpaper texture
- Window glass reflection: yes
- Lighting: natural daylight (daytime atmosphere)
- People: none
{custom_prompt}

【IMPORTANT】
Do not interpret or change the room's shape or proportions.
Keep the original contour lines and structure intact, only enhance textures to high-quality photorealistic finish."""


# Floor Plan Base Prompt (Isometric 3D Rendering)
FLOOR_PLAN_BASE_PROMPT = """Convert this entire floor plan into a photorealistic isometric 3D rendering while maintaining the bird's-eye view perspective.

{custom_prompt}
"""


@app.get("/api/info")
async def root():
    return {
        "status": "ok",
        "message": "AI Parse LINE Bot is running",
        "version": "2.1", # Version up
        "data_dir_exists": os.path.exists('/data'),
        "db_path": user_db.db_path if hasattr(user_db, 'db_path') else "Google Sheets"
    }

# ... (health check and stripe webhook remain same)

# ... (webhook and event handlers remain same)

async def handle_text_async(event_data: dict):
    """テキスト受信時の処理（非同期版）"""
    try:
        user_id = event_data["source"]["userId"]
        text = event_data["message"]["text"]
        reply_token = event_data["replyToken"]

        if user_id not in user_states:
            # 画像を送るよう促す
            await send_prompt_image_message(user_id, reply_token)
            return

        state = user_states[user_id]
        log(f"Current user state: {state}")

        # タイプ選択待ち
        if state.get("status") == "waiting_type":
            if text == "外観":
                user_states[user_id]["parse_type"] = "exterior"
                user_states[user_id]["status"] = "waiting_prompt"
                await send_prompt_input_message(user_id, reply_token, "exterior")
            elif text == "内観":
                user_states[user_id]["parse_type"] = "interior"
                user_states[user_id]["status"] = "waiting_prompt"
                await send_prompt_input_message(user_id, reply_token, "interior")
            elif text == "平面図":
                user_states[user_id]["parse_type"] = "floor_plan"
                user_states[user_id]["status"] = "waiting_prompt"
                await send_prompt_input_message(user_id, reply_token, "floor_plan")
            else:
                await send_type_selection(user_id, reply_token)
            return

        # プロンプト入力待ち
        if state.get("status") == "waiting_prompt":
            # カスタムプロンプトを取得（OKの場合は空）
            custom_prompt = "" if text.upper() == "OK" else f"\n・{text}"
            parse_type = state.get("parse_type", "exterior")

            # 生成開始
            await process_generation(
                user_id,
                state["image_message_id"],
                parse_type,
                custom_prompt,
                reply_token
            )
            del user_states[user_id]
            return

        # その他
        await send_prompt_image_message(user_id, reply_token)
    except Exception as e:
        log(f"Error in handle_text_async: {e}")
        import traceback
        traceback.print_exc()


# ... (send_welcome_message remains same)

async def send_type_selection(user_id: str, reply_token: str):
    """タイプ選択メッセージ送信"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text="生成するタイプを選んでください。",
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="外観",
                                        text="外観"
                                    )
                                ),
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="内観",
                                        text="内観"
                                    )
                                ),
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="平面図",
                                        text="平面図"
                                    )
                                ),
                            ]
                        )
                    )
                ]
            )
        )


async def send_prompt_input_message(user_id: str, reply_token: str, parse_type: str):
    """カスタムプロンプト入力メッセージ送信"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        if parse_type == "exterior":
            example_text = ("追加の指示があれば入力してください。\n\n"
                           "例：\n"
                           "・モダンな雰囲気で\n"
                           "・和風テイストに\n"
                           "・外壁をブラックに\n\n"
                           "そのまま生成する場合は「OK」と送信してください。")
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label="そのまま生成", text="OK")),
                QuickReplyItem(action=MessageAction(label="モダン", text="モダンな雰囲気で")),
                QuickReplyItem(action=MessageAction(label="和風", text="和風テイストで")),
            ]
        elif parse_type == "interior":
            example_text = ("追加の指示があれば入力してください。\n\n"
                           "例：\n"
                           "・モダンな雰囲気で\n"
                           "・北欧風インテリアに\n"
                           "・床を明るい木目に\n\n"
                           "そのまま生成する場合は「OK」と送信してください。")
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label="そのまま生成", text="OK")),
                QuickReplyItem(action=MessageAction(label="モダン", text="モダンな雰囲気で")),
                QuickReplyItem(action=MessageAction(label="北欧風", text="北欧風インテリアで")),
            ]
        else: # floor_plan
            example_text = ("追加の指示があれば入力してください。\n\n"
                           "例：\n"
                           "・木目でナチュラルに\n"
                           "・モノトーンでシックに\n"
                           "・部屋名を英語表記に\n\n"
                           "そのまま生成する場合は「OK」と送信してください。")
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label="そのまま生成", text="OK")),
                QuickReplyItem(action=MessageAction(label="ナチュラル", text="木目でナチュラルな雰囲気に")),
                QuickReplyItem(action=MessageAction(label="シック", text="モノトーンでシックな雰囲気に")),
            ]

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=example_text,
                        quick_reply=QuickReply(items=quick_reply_items)
                    )
                ]
            )
        )

# ... (send_prompt_image_message, send_limit_reached_message remain same)

async def process_generation(user_id: str, image_message_id: str, parse_type: str, custom_prompt: str, reply_token: str):
    """画像生成処理"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        # 処理開始メッセージ
        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text="✨ 4枚の画像を生成中です...\n⏱️ 完成した画像から順次お届けします！")
                ]
            )
        )

        try:
            # LINE から画像を取得
            image_content = await get_line_image(image_message_id)

            # プロンプト生成
            if parse_type == "interior":
                prompt = INTERIOR_BASE_PROMPT.format(custom_prompt=custom_prompt)
                type_name = "内観"
            elif parse_type == "exterior":
                prompt = EXTERIOR_BASE_PROMPT.format(custom_prompt=custom_prompt)
                type_name = "外観"
            else: # floor_plan
                prompt = FLOOR_PLAN_BASE_PROMPT.format(custom_prompt=custom_prompt)
                type_name = "平面図"
            
            # コールバック関数: 1枚生成されるたびに送信
            async def send_image_callback(index, url):
                if url:
                    await api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[
                                ImageMessage(
                                    original_content_url=url,
                                    preview_image_url=url
                                )
                            ]
                        )
                    )

            # 生成実行
            # services/kie_api.py の generate_parse_multi を呼び出す
            await kie_service.generate_parse_multi(image_content, prompt, count=4, callback=send_image_callback)

            # 使用回数をカウント
            user_db.increment_usage(user_id)
            remaining = user_db.get_remaining_count(user_id)
            
            if remaining <= 2:
                 await api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=f"残り生成可能回数: {remaining}回")]
                    )
                )

        except Exception as e:
            log(f"Process generation error: {e}")
            await api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text="申し訳ありません。画像生成中にエラーが発生しました。")]
                )
            )


@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "database": user_db.db_path,
        "data_writable": os.access('/data', os.W_OK) if os.path.exists('/data') else False
    }


@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """Stripe Webhookエンドポイント"""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    log("=== Stripe Webhook received ===")

    # 署名検証
    event = stripe_service.verify_webhook_signature(payload, signature)
    if not event:
        log("ERROR: Invalid Stripe signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event['type']
    log(f"Stripe event type: {event_type}")

    # サブスクリプション作成完了
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id') or session['metadata'].get('user_id')
        subscription_id = session.get('subscription')

        if user_id and subscription_id:
            # サブスクリプション期間を取得
            end_date = stripe_service.get_subscription_end_date(subscription_id)
            if end_date:
                # プレミアム設定
                user_db.set_premium(user_id, end_date)
                log(f"Premium activated for user: {user_id} until {end_date}")

                # LINEで通知
                await send_premium_activated_message(user_id)

    # サブスクリプション更新
    elif event_type == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        user_id = invoice['metadata'].get('user_id')

        if subscription_id:
            # 期間を延長
            end_date = stripe_service.get_subscription_end_date(subscription_id)
            if end_date and user_id:
                user_db.set_premium(user_id, end_date)
                log(f"Premium renewed for user: {user_id} until {end_date}")

    # サブスクリプションキャンセル
    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        user_id = subscription['metadata'].get('user_id')

        if user_id:
            user_db.cancel_premium(user_id)
            log(f"Premium canceled for user: {user_id}")

            # LINEで通知
            await send_premium_canceled_message(user_id)

    return {"status": "ok"}


def validate_signature(body: bytes, signature: str) -> bool:
    """LINE署名を検証"""
    hash_value = hmac.new(
        settings.LINE_CHANNEL_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode('utf-8')
    return hmac.compare_digest(signature, expected_signature)


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """LINE Webhookエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    log(f"=== Webhook received ===")
    log(f"Body length: {len(body_text)}")

    # 署名検証
    if not validate_signature(body, signature):
        log("ERROR: Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    log("Signature validated successfully")

    # 非同期イベント処理
    background_tasks.add_task(handle_events_async, body_text, signature)
    log("Background task added")

    return {"status": "ok"}


async def handle_events_async(body: str, signature: str):
    """非同期でイベントを処理"""
    import json
    from linebot.v3.webhooks import Event

    log("=== handle_events_async started ===")

    try:
        events_data = json.loads(body)
        log(f"Events data parsed: {len(events_data.get('events', []))} events")

        for event_data in events_data.get("events", []):
            event_type = event_data.get("type")
            log(f"Processing event type: {event_type}")

            if event_type == "follow":
                await handle_follow_async(event_data)
            elif event_type == "message":
                message_type = event_data.get("message", {}).get("type")
                log(f"Message type: {message_type}")
                if message_type == "image":
                    await handle_image_async(event_data)
                elif message_type == "text":
                    await handle_text_async(event_data)
    except Exception as e:
        log(f"Error in handle_events_async: {e}")
        import traceback
        traceback.print_exc()


async def handle_follow_async(event_data: dict):
    """友達追加時の処理（非同期版）"""
    user_id = event_data["source"]["userId"]
    reply_token = event_data["replyToken"]

    # ユーザー登録
    user_db.create_user(user_id)

    # ウェルカムメッセージ
    await send_welcome_message(user_id, reply_token)


async def handle_image_async(event_data: dict):
    """画像受信時の処理（非同期版）"""
    try:
        user_id = event_data["source"]["userId"]
        message_id = event_data["message"]["id"]
        reply_token = event_data["replyToken"]

        log(f"Image received from user: {user_id}, message_id: {message_id}")

        # 無料枠チェック
        remaining = user_db.get_remaining_count(user_id)
        if remaining <= 0:
            await send_limit_reached_message(user_id, reply_token)
            return

        # 画像を保存して状態を更新
        user_states[user_id] = {
            "image_message_id": message_id,
            "status": "waiting_type"  # 内観/外観選択待ち
        }

        log(f"User state updated: {user_states[user_id]}")

        # 内観/外観選択を促す
        await send_type_selection(user_id, reply_token)
    except Exception as e:
        log(f"Error in handle_image_async: {e}")
        import traceback
        traceback.print_exc()


async def send_welcome_message(user_id: str, reply_token: str):
    """ウェルカムメッセージ送信"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text="AI住宅パースへようこそ！\n\n"
                             "使い方はカンタン：\n"
                             "1. 建築パースの写真を送信\n"
                             "2. 内観/外観を選択\n"
                             "3. 追加指示を入力\n"
                             "4. 4枚のパースが完成！\n\n"
                             "毎月3回まで無料でお試しいただけます。\n\n"
                             "さっそく写真を送ってみてください！"
                    )
                ]
            )
        )







async def send_prompt_image_message(user_id: str, reply_token: str):
    """画像送信を促すメッセージ"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        remaining = user_db.get_remaining_count(user_id)

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=f"建築パースの写真を送ってください。\n\n"
                             f"今月の残り回数: {remaining}回"
                    )
                ]
            )
        )


async def send_limit_reached_message(user_id: str, reply_token: str):
    """無料枠上限到達メッセージ"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        # プレミアムユーザーかチェック
        user = user_db.get_user(user_id)
        is_premium = user and user["is_premium"]

        # Stripe決済リンクを生成
        payment_url = stripe_service.create_payment_link(user_id)
        if not payment_url:
            # フォールバック: 固定URL
            payment_url = "https://buy.stripe.com/test_XXXXXX"  # Stripeダッシュボードで取得

        if is_premium:
            # プレミアムユーザーが15回使い切った場合
            message = (
                "今月のプレミアム枠（15回）を使い切りました。\n\n"
                "来月1日に自動的にリセットされます。\n"
                "引き続きご利用ありがとうございます！"
            )
        else:
            # 無料ユーザーが3回使い切った場合
            message = (
                "今月の無料枠（3回）を使い切りました。\n\n"
                "🌟 プレミアムプラン: 月額1,980円\n"
                "✨ 月15回まで生成可能（1回4枚）\n"
                "💰 コスト: 1回あたり約132円\n\n"
                f"お申し込みはこちら:\n{payment_url}"
            )

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=message)]
            )
        )




async def get_line_image(message_id: str) -> bytes:
    """LINEから画像を取得"""
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.content


async def send_premium_activated_message(user_id: str):
    """プレミアム有効化通知"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[
                    TextMessage(
                        text="🎉 プレミアムプランが有効になりました！\n\n"
                             "✨ 月15回まで生成可能（1回4枚）\n"
                             "📅 毎月1日に回数リセット\n\n"
                             "ご利用ありがとうございます！"
                    )
                ]
            )
        )


async def send_premium_canceled_message(user_id: str):
    """プレミアムキャンセル通知"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[
                    TextMessage(
                        text="プレミアムプランが終了しました。\n\n"
                             "引き続き月3回まで無料でご利用いただけます。\n\n"
                             "またのご利用をお待ちしております！"
                    )
                ]
            )
        )


# Mount the homepage static files at the root
# This must be at the end to avoid overriding other routes
if os.path.exists("homepage"):
    app.mount("/", StaticFiles(directory="homepage", html=True), name="homepage")
else:
    log("Homepage directory not found, skipping mount.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
