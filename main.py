"""
LINE Bot for AI Architectural Rendering
住宅営業マン向けAIパース生成LINEボット
"""
import os
import httpx
import hmac
import hashlib
import base64
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
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

app = FastAPI(title="AI Parse LINE Bot")

# LINE Bot設定
configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)

# ユーザーDB
user_db = UserDB()

# ユーザーの状態管理（メモリ上、本番はRedis推奨）
user_states = {}

# 外観用ベースプロンプト
EXTERIOR_BASE_PROMPT = """添付の建築パースをフォトリアルにしてください。
建物の形状・構成・アングル・奥行・カメラ位置・パースラインは絶対に変更しないでください。
素材・質感・光の表現だけを実写に寄せてください。

【必ず守ってほしい内容】
・外観の形状を一切変えない
・窓の位置、壁のライン、屋根形状、陰影の付き方の方向はそのまま
・広角率を変えない
・縦横比（例：3:4、横長）を維持
・背景の構成を変えない（変更したい場合は指定する）

【今回のフォトリアル化条件】
・外壁は窯業系サイディングの質感を出す
・道路はアスファルトの質感を出す
・背景：住宅街
・コンクリート反射：なし
・窓ガラス反射：あり
・天候：晴れ
・人物：不要
{custom_prompt}

【重要】
建物の形状や寸法感が変わるような解釈は絶対にしないでください。
元画像の輪郭線と構造はそのまま、質感だけを高精細フォトリアルに仕上げてください。"""

# 内観用ベースプロンプト
INTERIOR_BASE_PROMPT = """添付の建築内観パースをフォトリアルにしてください。
部屋の形状・構成・アングル・奥行・カメラ位置・パースラインは絶対に変更しないでください。
素材・質感・光の表現だけを実写に寄せてください。

【必ず守ってほしい内容】
・部屋の形状を一切変えない
・窓の位置、壁のライン、天井形状、陰影の付き方の方向はそのまま
・広角率を変えない
・縦横比（例：3:4、横長）を維持
・家具・設備の配置を変えない

【今回のフォトリアル化条件】
・床材はフローリングの質感を出す
・壁は白いクロスの質感を出す
・天井は白いクロスの質感を出す
・窓ガラス反射：あり
・照明：自然光メイン（昼間の雰囲気）
・人物：不要
{custom_prompt}

【重要】
部屋の形状や寸法感が変わるような解釈は絶対にしないでください。
元画像の輪郭線と構造はそのまま、質感だけを高精細フォトリアルに仕上げてください。"""


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Parse LINE Bot is running"}


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

    # 署名検証
    if not validate_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 非同期イベント処理
    background_tasks.add_task(handle_events_async, body_text, signature)

    return {"status": "ok"}


async def handle_events_async(body: str, signature: str):
    """非同期でイベントを処理"""
    import json
    from linebot.v3.webhooks import Event

    try:
        events_data = json.loads(body)

        for event_data in events_data.get("events", []):
            event_type = event_data.get("type")

            if event_type == "follow":
                await handle_follow_async(event_data)
            elif event_type == "message":
                message_type = event_data.get("message", {}).get("type")
                if message_type == "image":
                    await handle_image_async(event_data)
                elif message_type == "text":
                    await handle_text_async(event_data)
    except Exception as e:
        print(f"Error in handle_events_async: {e}")
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

        print(f"Image received from user: {user_id}, message_id: {message_id}")

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

        print(f"User state updated: {user_states[user_id]}")

        # 内観/外観選択を促す
        await send_type_selection(user_id, reply_token)
    except Exception as e:
        print(f"Error in handle_image_async: {e}")
        import traceback
        traceback.print_exc()


async def handle_text_async(event_data: dict):
    """テキスト受信時の処理（非同期版）"""
    try:
        user_id = event_data["source"]["userId"]
        text = event_data["message"]["text"]
        reply_token = event_data["replyToken"]

        print(f"Text received from user: {user_id}, text: {text}")

        if user_id not in user_states:
            # 画像を送るよう促す
            await send_prompt_image_message(user_id, reply_token)
            return

        state = user_states[user_id]
        print(f"Current user state: {state}")

        # 内観/外観選択待ち
        if state.get("status") == "waiting_type":
            if text == "外観":
                user_states[user_id]["parse_type"] = "exterior"
                user_states[user_id]["status"] = "waiting_prompt"
                await send_prompt_input_message(user_id, reply_token, "exterior")
            elif text == "内観":
                user_states[user_id]["parse_type"] = "interior"
                user_states[user_id]["status"] = "waiting_prompt"
                await send_prompt_input_message(user_id, reply_token, "interior")
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
            print(f"User state deleted after generation")
            return

        # その他
        await send_prompt_image_message(user_id, reply_token)
    except Exception as e:
        print(f"Error in handle_text_async: {e}")
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




async def send_type_selection(user_id: str, reply_token: str):
    """内観/外観選択メッセージ送信"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text="外観パースですか？内観パースですか？",
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
                           "・外壁をブラックに\n"
                           "・緑を多めに\n\n"
                           "そのまま生成する場合は「OK」と送信してください。")
        else:
            example_text = ("追加の指示があれば入力してください。\n\n"
                           "例：\n"
                           "・モダンな雰囲気で\n"
                           "・和風テイストに\n"
                           "・床を無垢材に\n"
                           "・観葉植物を追加\n\n"
                           "そのまま生成する場合は「OK」と送信してください。")

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=example_text,
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="そのまま生成",
                                        text="OK"
                                    )
                                ),
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="モダン",
                                        text="モダンな雰囲気で"
                                    )
                                ),
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="和風",
                                        text="和風テイストで"
                                    )
                                ),
                                QuickReplyItem(
                                    action=MessageAction(
                                        label="ナチュラル",
                                        text="ナチュラルな雰囲気で"
                                    )
                                ),
                            ]
                        )
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

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text="今月の無料枠（3回）を使い切りました。\n\n"
                             "無制限プラン: 月額1,980円\n"
                             "お申し込みはこちら:\n"
                             "https://example.com/subscribe"  # TODO: 課金ページURL
                    )
                ]
            )
        )


async def process_generation(user_id: str, image_message_id: str, parse_type: str, custom_prompt: str, reply_token: str):
    """画像生成処理（4枚同時生成）"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        # 処理開始メッセージ
        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text="4枚同時生成中です...1〜2分ほどお待ちください")
                ]
            )
        )

        try:
            # LINE から画像を取得
            image_content = await get_line_image(image_message_id)

            # プロンプト生成（内観/外観で切り替え）
            if parse_type == "interior":
                prompt = INTERIOR_BASE_PROMPT.format(custom_prompt=custom_prompt)
                type_name = "内観"
            else:
                prompt = EXTERIOR_BASE_PROMPT.format(custom_prompt=custom_prompt)
                type_name = "外観"

            # KIE.AI で4枚同時生成
            result_urls = await generate_parse_multi(image_content, prompt, count=4)

            # 成功した画像をフィルタリング
            successful_urls = [url for url in result_urls if url is not None]

            if successful_urls:
                # 使用回数をカウント
                user_db.increment_usage(user_id)
                remaining = user_db.get_remaining_count(user_id)

                # 結果を送信（最大5メッセージまで）
                messages = []
                for url in successful_urls[:4]:  # 最大4枚
                    messages.append(
                        ImageMessage(
                            original_content_url=url,
                            preview_image_url=url
                        )
                    )

                messages.append(
                    TextMessage(
                        text=f"完成しました！（{type_name}パース {len(successful_urls)}枚）\n\n"
                             f"今月の残り回数: {remaining}回"
                    )
                )

                await api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=messages
                    )
                )
            else:
                await api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[
                            TextMessage(text="生成に失敗しました。もう一度お試しください。")
                        ]
                    )
                )

        except Exception as e:
            print(f"Generation error: {e}")
            await api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[
                        TextMessage(text="エラーが発生しました。もう一度お試しください。")
                    ]
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
