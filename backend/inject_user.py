import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.utils.conn import conn_db
from app.utils import gen_md5

salt = 'arlsalt!@#'
username = 'admin'
password = 'arlpass'

db_user = conn_db('user')
query = {"username": username}
if not db_user.find_one(query):
    db_user.insert_one({"username": username, "password": gen_md5(salt + password)})
    print("✅ admin inserted!")
else:
    print("ℹ️ admin already exists, skipping password reset.")
