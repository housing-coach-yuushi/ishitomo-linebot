import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.user_db import UserDB
# config.pyの値を一時的に上書きするためのダミー設定は不要
# ローカルの .env またはデフォルト値が読まれるはず

# .envを読み込む（念の為）
from dotenv import load_dotenv
load_dotenv()

print("Initializing UserDB...", flush=True)
try:
    # これで __init__ が走り、_init_worksheets も呼ばれる
    db = UserDB()
    print("UserDB initialized successfully!", flush=True)
    print("Check your spreadsheet now.", flush=True)
except Exception as e:
    print(f"Error initializing UserDB: {e}", flush=True)
    import traceback
    traceback.print_exc()
