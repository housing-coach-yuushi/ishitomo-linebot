"""
LINE Bot for AI Architectural Rendering
住宅営業マン向けAIパース生成LINEボット
"""
import os
import asyncio
import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot.v3 import WebhookHandler
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
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    FollowEvent,
    PostbackEvent,
)
from linebot.v3.exceptions import InvalidSignatureError

from config import settings
from services.kie_api import generate_parse
from services.user_db import UserDB

app = FastAPI(title="AI Parse LINE Bot")

# LINE Bot設定
configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

# ユーザーDB
user_db = UserDB()

# ユーザーの状態管理（メモリ上、本番はRedis推奨）
user_states = {}

# ベースプロンプト（非公開）
BASE_PROMPT = """添付の建築パースをフォトリアルにしてください。
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


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Parse LINE Bot is running"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """LINE Webhookエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return {"status": "ok"}


@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """友達追加時の処理"""
    user_id = event.source.user_id

    # ユーザー登録
    user_db.create_user(user_id)

    # ウェルカムメッセージ
    asyncio.create_task(send_welcome_message(user_id, event.reply_token))


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
                             "2. 追加指示を入力（モダン、和風など）\n"
                             "3. 30秒で完成！\n\n"
                             "毎月3回まで無料でお試しいただけます。\n\n"
                             "さっそく写真を送ってみてください！"
                    )
                ]
            )
        )


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event: MessageEvent):
    """画像受信時の処理"""
    user_id = event.source.user_id
    message_id = event.message.id

    # 無料枠チェック
    remaining = user_db.get_remaining_count(user_id)
    if remaining <= 0:
        asyncio.create_task(send_limit_reached_message(user_id, event.reply_token))
        return

    # 画像を保存して状態を更新
    user_states[user_id] = {
        "image_message_id": message_id,
        "status": "waiting_prompt"
    }

    # カスタムプロンプト入力を促す
    asyncio.create_task(send_prompt_input_message(user_id, event.reply_token))


async def send_prompt_input_message(user_id: str, reply_token: str):
    """カスタムプロンプト入力メッセージ送信"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text="追加の指示があれば入力してください。\n\n"
                             "例：\n"
                             "・モダンな雰囲気で\n"
                             "・和風テイストに\n"
                             "・外壁をブラックに\n"
                             "・緑を多めに\n\n"
                             "そのまま生成する場合は「OK」と送信してください。",
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


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event: MessageEvent):
    """テキスト受信時の処理"""
    user_id = event.source.user_id
    text = event.message.text

    # プロンプト入力待ちの場合
    if user_id in user_states and user_states[user_id].get("status") == "waiting_prompt":
        # カスタムプロンプトを取得（OKの場合は空）
        custom_prompt = "" if text.upper() == "OK" else f"\n・{text}"

        # 生成開始
        asyncio.create_task(
            process_generation(
                user_id,
                user_states[user_id]["image_message_id"],
                custom_prompt,
                event.reply_token
            )
        )
        del user_states[user_id]
    else:
        # 画像を送るよう促す
        asyncio.create_task(send_prompt_image_message(user_id, event.reply_token))


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


async def process_generation(user_id: str, image_message_id: str, custom_prompt: str, reply_token: str):
    """画像生成処理"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)

        # 処理開始メッセージ
        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text="生成中です...30秒ほどお待ちください")
                ]
            )
        )

        try:
            # LINE から画像を取得
            image_content = await get_line_image(image_message_id)

            # プロンプト生成（カスタムプロンプトを追加）
            prompt = BASE_PROMPT.format(custom_prompt=custom_prompt)

            # KIE.AI で生成
            result_url = await generate_parse(image_content, prompt)

            if result_url:
                # 使用回数をカウント
                user_db.increment_usage(user_id)
                remaining = user_db.get_remaining_count(user_id)

                # 結果を送信
                await api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[
                            ImageMessage(
                                original_content_url=result_url,
                                preview_image_url=result_url
                            ),
                            TextMessage(
                                text=f"完成しました！\n\n"
                                     f"今月の残り回数: {remaining}回"
                            )
                        ]
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
