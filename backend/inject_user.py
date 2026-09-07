import os
import sys

# 确保无论从任何工作目录调用，均能准确加载 backend 目录下的 app 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.utils.conn import conn_db
from app.utils import gen_md5

salt = 'arlsalt!@#'
username = 'admin'
password = 'arlpass'

db_user = conn_db('user')
query = {"username": username}
is_reset = '--reset' in sys.argv

user = db_user.find_one(query)
if not user:
    db_user.insert_one({"username": username, "password": gen_md5(salt + password)})
    print("✅ admin inserted!")
elif is_reset:
    db_user.update_one(query, {"$set": {"password": gen_md5(salt + password)}})
    print("✅ admin password successfully reset to arlpass!")
else:
    print("ℹ️ admin already exists, skipping password reset (pass --reset to force reset).")
