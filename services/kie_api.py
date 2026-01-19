"""
KIE.AI API連携（LINE Bot用・非同期版）
"""
import asyncio
import base64
import io
import json
from typing import Optional, List

import httpx
from PIL import Image

from config import settings

# API URLs
CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"


def image_bytes_to_base64(image_bytes: bytes) -> str:
    """画像バイトをBase64文字列に変換"""
    image = Image.open(io.BytesIO(image_bytes))

    # リサイズ（大きすぎる場合）
    max_size = 1024
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # RGBA -> RGB
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGB")

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=90)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_str}"


async def upload_image(base64_image: str) -> Optional[str]:
    """画像をKIE.AIにアップロード"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.KIEAI_API_KEY}"
    }
    payload = {
        "base64Data": base64_image,
        "filename": "upload.jpg",
        "uploadPath": "temp"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(UPLOAD_URL, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    return data["data"]["downloadUrl"]
        except Exception as e:
            print(f"Upload error: {e}")
    return None


async def get_webhook_token() -> Optional[str]:
    """Webhook.siteからトークン取得"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(3):
            try:
                res = await client.post("https://webhook.site/token")
                if res.status_code in [200, 201]:
                    return res.json()["uuid"]
            except Exception as e:
                print(f"Webhook token error (attempt {i+1}): {e}")
            await asyncio.sleep(1)
    return None


async def create_task(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """KIE.AIタスク作成"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.KIEAI_API_KEY}"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(CREATE_TASK_URL, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 200:
                    return data["data"]["taskId"], None
                else:
                    return None, data.get("msg")
            else:
                return None, f"HTTP {res.status_code}"
        except Exception as e:
            return None, str(e)


async def poll_webhook(uuid: str, timeout: int = 120) -> Optional[str]:
    """Webhookをポーリングして結果URLを取得"""
    poll_url = f"https://webhook.site/token/{uuid}/requests"

    async with httpx.AsyncClient(timeout=10.0) as client:
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                res = await client.get(poll_url)
                if res.status_code == 200:
                    data_list = res.json().get("data", [])
                    for req in data_list:
                        content = req.get("content")
                        if content:
                            try:
                                body = json.loads(content)
                                data_body = body.get("data", {})
                                state = data_body.get("state")

                                if state == "success":
                                    if "resultUrls" in data_body and data_body["resultUrls"]:
                                        return data_body["resultUrls"][0]
                                    elif "resultJson" in data_body:
                                        rj = json.loads(data_body["resultJson"])
                                        if "resultUrls" in rj:
                                            return rj["resultUrls"][0]
                                elif state == "fail":
                                    return None
                            except:
                                pass
            except Exception as e:
                print(f"Polling error: {e}")

            await asyncio.sleep(3)

    return None


async def generate_parse_single(image_url: str, prompt: str, model: str) -> Optional[str]:
    """
    単一の画像生成タスクを実行

    Args:
        image_url: アップロード済み画像URL
        prompt: 生成プロンプト
        model: 使用するモデル

    Returns:
        生成された画像のURL、失敗時はNone
    """
    try:
        # Webhookトークン取得
        wh_uuid = await get_webhook_token()
        if not wh_uuid:
            print(f"Webhook token failed for {model}")
            return None

        callback_url = f"https://webhook.site/{wh_uuid}"

        # タスク作成
        task_payload = {
            "model": model,
            "callBackUrl": callback_url,
            "input": {
                "prompt": prompt,
                "image_urls": [image_url],
                "aspect_ratio": "16:9",
                "quality": "high"
            }
        }

        task_id, error = await create_task(task_payload)
        if not task_id:
            print(f"Task creation failed for {model}: {error}")
            return None

        # 結果をポーリング
        result_url = await poll_webhook(wh_uuid, timeout=180)
        return result_url

    except Exception as e:
        print(f"Generation error for {model}: {e}")
        return None


async def generate_parse(image_bytes: bytes, prompt: str) -> Optional[str]:
    """
    画像からパースを生成（単一生成・後方互換用）

    Args:
        image_bytes: 画像のバイトデータ
        prompt: 生成プロンプト

    Returns:
        生成された画像のURL、失敗時はNone
    """
    try:
        # 1. 画像をBase64に変換
        base64_image = image_bytes_to_base64(image_bytes)

        # 2. 画像をアップロード
        image_url = await upload_image(base64_image)
        if not image_url:
            print("Image upload failed")
            return None

        # 3. 単一生成
        return await generate_parse_single(image_url, prompt, "seedream/4.5-edit")

    except Exception as e:
        print(f"Generation error: {e}")
        return None


async def generate_parse_multi(image_bytes: bytes, prompt: str, count: int = 4) -> list[Optional[str]]:
    """
    画像からパースを複数枚同時生成

    Args:
        image_bytes: 画像のバイトデータ
        prompt: 生成プロンプト
        count: 生成枚数（デフォルト4枚）

    Returns:
        生成された画像のURLリスト
    """
    # 使用する4つの異なるモデル/エンジン
    MODELS = [
        "seedream/4.5-edit",
        "flux/1.1-pro-ultra",
        "ideogram/v2",
        "recraft/v3",
    ]

    try:
        # 1. 画像をBase64に変換
        base64_image = image_bytes_to_base64(image_bytes)

        # 2. 画像をアップロード（1回だけ）
        image_url = await upload_image(base64_image)
        if not image_url:
            print("Image upload failed")
            return [None] * count

        # 3. 4つのモデルで同時生成
        tasks = []
        for i in range(min(count, len(MODELS))):
            model = MODELS[i]
            tasks.append(generate_parse_single(image_url, prompt, model))

        # 全タスクを並列実行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果を整理（例外はNoneに変換）
        urls = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Task exception: {result}")
                urls.append(None)
            else:
                urls.append(result)

        return urls

    except Exception as e:
        print(f"Multi-generation error: {e}")
        return [None] * count
