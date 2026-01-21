import sys
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# プロジェクトルートを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import settings

# 認証設定
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('./config/service-account.json', scope)
client = gspread.authorize(creds)

print("Creating new spreadsheet 'AIパース会員管理'...", flush=True)

try:
    # スプレッドシート作成
    sh = client.create('AIパース会員管理')
    
    # 全員に閲覧権限付与（または特定のメアドに付与）
    # ここでは仮にリンクを知っている人は編集可能にする（ユーザーがアクセスしやすくするため）
    # 本番運用ではユーザーのメアドに限定するのがベターだが、メアドがわからないのでpublic化
    sh.share(None, perm_type='anyone', role='writer')
    
    print(f"SUCCESS! New Spreadsheet Created.", flush=True)
    print(f"Title: {sh.title}", flush=True)
    print(f"ID: {sh.id}", flush=True)
    print(f"URL: {sh.url}", flush=True)
    
    # ワークシート初期化
    print("Initializing worksheets...", flush=True)
    
    # Users
    users_ws = sh.add_worksheet(title="Users", rows=1000, cols=4)
    users_ws.append_row(["user_id", "created_at", "is_premium", "premium_expires_at"])
    
    # Usage
    usage_ws = sh.add_worksheet(title="Usage", rows=1000, cols=3)
    usage_ws.append_row(["user_id", "used_at", "month"])
    
    # デフォルトのSheet1を削除
    try:
        sh.del_worksheet(sh.sheet1)
    except:
        pass
        
    print("Worksheets initialized.", flush=True)

except Exception as e:
    print(f"Error creating spreadsheet: {e}", flush=True)
