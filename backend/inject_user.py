import os
import sys
import secrets
import tempfile

# 确保无论从任何工作目录调用，均能准确加载 backend 目录下的 app 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.utils.conn import conn_db
from app.utils.credentials import hash_password, validate_new_password

def ensure_admin(db_user, *, reset=False, password=None, password_file='/tmp/arl_initial_admin_password'):
    query = {'username': 'admin'}
    user = db_user.find_one(query)
    if user and not reset:
        print('ℹ️ admin already exists, skipping password reset (pass --reset to force reset).')
        return
    generated = not password
    password = password or secrets.token_urlsafe(24)
    validate_new_password(password)
    if generated:
        # Never print the password into Docker/journal logs.
        fd, temporary = tempfile.mkstemp(prefix='arl_initial_admin_', dir=os.path.dirname(password_file))
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(password + '\n')
            os.replace(temporary, password_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(f'管理员随机初始密码已保存至容器 {password_file}（权限 0600）。')
    if not user:
        db_user.insert_one({'username': 'admin', 'password': hash_password(password)})
        print('✅ admin inserted!')
    else:
        db_user.update_one(query, {'$set': {'password': hash_password(password), 'token': None},
                                   '$unset': {'token_expire_at': ''}})
        print('✅ admin password reset; previous login session revoked.')
    if not generated and os.path.exists(password_file):
        os.unlink(password_file)


if __name__ == '__main__':
    ensure_admin(conn_db('user'), reset='--reset' in sys.argv, password=os.environ.get('ARL_ADMIN_PASSWORD'))
