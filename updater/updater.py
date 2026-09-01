import os
import sys
import json
import time
import subprocess
import threading
import re
import uuid
import hashlib
import string
import random
import ipaddress
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

TOKEN_FILE = "/tmp/arl_update_token"
LOG_FILE = "/tmp/arl_update.log"
PORT = 8888

update_thread = None
dynamic_progress = {}
config_lock = threading.Lock()

CGNAT_NET = ipaddress.ip_network('100.64.0.0/10')

def is_trusted_ip(client_ip: str) -> bool:
    """
    基于第一性原理严格判定请求 IP 是否来自本地回环或私有网段 (RFC 1918 / RFC 6598 CGNAT / Link-local)
    杜绝 172.x 公网 IP 误放行与非标私有网段误拦截
    """
    if not client_ip:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
        return ip.is_loopback or ip.is_private or ip.is_link_local or (ip.version == 4 and ip in CGNAT_NET)
    except ValueError:
        return False

WEB_CONTAINER = "arl-web-prod"
FRONTEND_CONTAINER = "arl-frontend-prod"

def get_web_container():
    return WEB_CONTAINER

def get_frontend_container():
    return FRONTEND_CONTAINER

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_apr1_htpasswd(username, password):
    """
    生成标准 Apache MD5 (APR1) 格式的 htpasswd 单行凭据
    """
    # 优先使用系统 openssl 工具生成
    try:
        res = subprocess.run(["openssl", "passwd", "-apr1", password], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if res.returncode == 0 and res.stdout.strip().startswith("$apr1$"):
            return f"{username}:{res.stdout.strip()}\n"
    except Exception:
        pass

    # 纯 Python 兜底实现 APR1-MD5 算法
    chars = string.ascii_letters + string.digits
    salt = "".join(random.choice(chars) for _ in range(8))[:8]
    
    ctx = hashlib.md5((password + "$apr1$" + salt).encode("utf-8"))
    final = hashlib.md5((password + salt + password).encode("utf-8")).digest()
    
    for i in range(len(password), 0, -16):
        ctx.update(final[:min(i, 16)])
        
    i = len(password)
    while i > 0:
        if i & 1:
            ctx.update(b"\x00")
        else:
            ctx.update(password[:1].encode("utf-8"))
        i >>= 1
        
    final = ctx.digest()
    
    for i in range(1000):
        ctx1 = hashlib.md5()
        if i & 1:
            ctx1.update(password.encode("utf-8"))
        else:
            ctx1.update(final)
        if i % 3:
            ctx1.update(salt.encode("utf-8"))
        if i % 7:
            ctx1.update(password.encode("utf-8"))
        if i & 1:
            ctx1.update(final)
        else:
            ctx1.update(password.encode("utf-8"))
        final = ctx1.digest()
        
    def to64(v, n):
        itoa64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        res = ""
        while n > 0:
            res += itoa64[v & 0x3f]
            v >>= 6
            n -= 1
        return res
        
    output = "$apr1$" + salt + "$"
    v = (final[0] << 16) | (final[6] << 8) | final[12]
    output += to64(v, 4)
    v = (final[1] << 16) | (final[7] << 8) | final[13]
    output += to64(v, 4)
    v = (final[2] << 16) | (final[8] << 8) | final[14]
    output += to64(v, 4)
    v = (final[3] << 16) | (final[9] << 8) | final[15]
    output += to64(v, 4)
    v = (final[4] << 16) | (final[10] << 8) | final[5]
    output += to64(v, 4)
    v = final[11]
    output += to64(v, 2)
    return f"{username}:{output}\n"

def ensure_htpasswd_file(base_dir: str, username: str = None, password: str = None):
    """
    自愈/生成宿主机 ./frontend/.htpasswd 文件 (原地写入以保持 Docker Bind Mount inode 一致)
    """
    htpasswd_path = os.path.join(base_dir, "frontend", ".htpasswd")
    os.makedirs(os.path.dirname(htpasswd_path), exist_ok=True)
    
    # 若提供了新账密，则直接重新生成
    if username and password:
        content = generate_apr1_htpasswd(username, password)
        with open(htpasswd_path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    # 若未提供自定义账密，且文件不存在或为空，则补齐默认 admin / arl_next
    if not os.path.exists(htpasswd_path) or os.path.getsize(htpasswd_path) == 0:
        content = "admin:$apr1$i/Qqu0mp$6rhjb2tWaFFEqpeDcr4Su/\n"
        with open(htpasswd_path, "w", encoding="utf-8") as f:
            f.write(content)

def check_nginx_auth_status(content: str) -> bool:
    """
    检查 Nginx 配置中的顶层 auth_basic 指令状态
    """
    first_loc = re.search(r'location\s*[\^~=]*\s*/', content)
    server_scope = content[:first_loc.start()] if first_loc else content
    match = re.search(r'^\s*auth_basic\s+([^;]+);', server_scope, re.MULTILINE)
    if match:
        val = match.group(1).strip().strip('"').strip("'")
        return val.lower() != "off"
    return False

def update_nginx_auth_config(content: str, enable: bool) -> str:
    """
    更新 Nginx 配置中的顶层 auth_basic 指令，并确保 /api/ 与 /update_stream/ 等路径保持 auth_basic off
    """
    first_loc = re.search(r'location\s*[\^~=]*\s*/', content)
    if first_loc:
        server_scope = content[:first_loc.start()]
        rest_scope = content[first_loc.start():]
    else:
        server_scope = content
        rest_scope = ""

    new_auth_val = 'auth_basic "Restricted Access - AntiScan";' if enable else 'auth_basic off;'
    
    if re.search(r'^\s*auth_basic\s+[^;]+;', server_scope, re.MULTILINE):
        server_scope = re.sub(
            r'^(\s*)auth_basic\s+[^;]+;',
            rf'\1{new_auth_val}',
            server_scope,
            count=1,
            flags=re.MULTILINE
        )
    else:
        server_scope = re.sub(
            r'(server\s*\{[^\n]*\n)',
            rf'\1    # 开启 HTTP Basic Auth 阻挡被动扫描\n    {new_auth_val}\n    auth_basic_user_file /etc/nginx/.htpasswd;\n',
            server_scope,
            count=1
        )
        
    # 确保 /api/ 块内部的 auth_basic 始终为 off
    rest_scope = re.sub(
        r'(location\s+\^?~?\s*/api/[^{]*\{[^}]*?auth_basic\s+)[^;]+;',
        r'\g<1>off;',
        rest_scope,
        flags=re.DOTALL
    )
    # 确保 /update_stream/ 块内部的 auth_basic 始终为 off
    rest_scope = re.sub(
        r'(location\s+\^?~?\s*/update_stream/[^{]*\{[^}]*?auth_basic\s+)[^;]+;',
        r'\g<1>off;',
        rest_scope,
        flags=re.DOTALL
    )

    return server_scope + rest_scope

class PollingHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Update-Token")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _read_json_body(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length).decode('utf-8', errors='ignore')
                return json.loads(raw_body)
        except Exception:
            pass
        return {}

    def _extract_token(self, parsed_url, body_data=None):
        # 1. Header: Authorization: Bearer <token>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        
        # 2. Header: X-Update-Token
        custom_header = self.headers.get("X-Update-Token", "").strip()
        if custom_header:
            return custom_header
            
        # 3. POST JSON Body
        if body_data and isinstance(body_data, dict) and body_data.get("token"):
            return str(body_data.get("token")).strip()
            
        # 4. Query Parameter (兼容 GET)
        query_params = parse_qs(parsed_url.query)
        return query_params.get("token", [""])[0].strip()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        
        client_ip = self.client_address[0]
        if not is_trusted_ip(client_ip):
            self.send_response(403)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'Forbidden: External IP access denied')
            return

        body_data = self._read_json_body()
        
        if parsed_url.path == "/update/toggle_auth":
            self.handle_toggle_auth(parsed_url, body_data)
        elif parsed_url.path == "/update/trigger":
            self.handle_trigger(parsed_url, body_data)
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        client_ip = self.client_address[0]
        if not is_trusted_ip(client_ip):
            self.send_response(403)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'Forbidden: External IP access denied')
            return

        if parsed_url.path == "/update/trigger":
            self.handle_trigger(parsed_url)
        elif parsed_url.path == "/update/log":
            self.handle_log(parsed_url)
        elif parsed_url.path == "/update/auth_status":
            self.handle_auth_status()
        elif parsed_url.path == "/update/toggle_auth":
            self.handle_toggle_auth(parsed_url)
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def _authorize_token(self, token):
        """校验更新令牌；若 Docker 守护进程停机导致容器内校验不可达，先自愈再重试一次。"""
        if self.verify_token(token):
            return True
        # daemon 停机会使 docker exec 失败而被误判为无效令牌，
        # 先尝试恢复 daemon 再重试，确保 ensure_docker_daemon 自愈链路真正可达
        if not self._docker_info_ok() and self.ensure_docker_daemon():
            return self.verify_token(token)
        return False

    def handle_trigger(self, parsed_url, body_data=None):
        global update_thread, dynamic_progress
        token = self._extract_token(parsed_url, body_data)
        
        if not self._authorize_token(token):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Invalid token"}')
            return

        # Invalidate token inside container
        try:
            subprocess.run(["docker", "exec", get_web_container(), "rm", "-f", TOKEN_FILE])
        except Exception:
            pass

        # clear log file
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("⏳ 正在初始化更新任务...\n")
        
        dynamic_progress.clear()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "message": "Update triggered"}')

        # Start update in background if not already running
        if update_thread is None or not update_thread.is_alive():
            update_thread = threading.Thread(target=self.run_update_task)
            update_thread.start()

    def handle_log(self, parsed_url=None):
        query_params = parse_qs(parsed_url.query) if parsed_url else {}
        raw_offset = query_params.get("offset", [None])[0]
        
        # 1. 增量 Byte-Offset 日志拉取模式 (降低90%网络带宽与前端DOM消耗)
        if raw_offset is not None:
            try:
                offset = int(raw_offset)
            except ValueError:
                offset = 0
                
            chunk = ""
            new_offset = offset
            full_log = ""
            
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(offset)
                        chunk = f.read()
                        new_offset = f.tell()
                        f.seek(0)
                        full_log = f.read()
                except Exception:
                    pass
                    
            resp_data = {
                "offset": new_offset,
                "chunk": chunk,
                "progress": dynamic_progress.copy(),
                "done": "[DONE]" in full_log,
                "error": "[ERROR]" in full_log
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(resp_data, ensure_ascii=False).encode('utf-8'))
            return

        # 2. 全量日志纯文本回退兼容模式
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        
        content = ""
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "Waiting for logs...\n"
            
        for layer, prog in dynamic_progress.items():
            content += f"🔄 {layer}: {prog}\n"
            
        self.wfile.write(content.encode('utf-8'))

    def handle_auth_status(self):
        enabled = True
        base_dir = get_base_dir()
        conf_prod = os.path.join(base_dir, "frontend", "default.conf.prod")
        
        # 1. 优先读取宿主机上的 default.conf.prod
        content = None
        if os.path.exists(conf_prod):
            try:
                with open(conf_prod, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                pass

        # 2. 如果宿主机文件未读取到，尝试从前端容器中读取
        if not content:
            frontend_container = get_frontend_container()
            try:
                result = subprocess.run(["docker", "exec", frontend_container, "cat", "/etc/nginx/conf.d/default.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                if result.returncode == 0:
                    content = result.stdout
            except Exception:
                pass

        if content:
            enabled = check_nginx_auth_status(content)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "enabled": enabled}).encode('utf-8'))

    def handle_toggle_auth(self, parsed_url, body_data=None):
        token = self._extract_token(parsed_url, body_data)
        
        # 解析 enable 状态
        enable = True
        username = None
        password = None
        if body_data and isinstance(body_data, dict):
            if "enable" in body_data:
                enable = bool(body_data["enable"])
            username = body_data.get("username")
            password = body_data.get("password")
        else:
            query_params = parse_qs(parsed_url.query)
            enable = query_params.get("enable", ["true"])[0].lower() == "true"
            username = query_params.get("username", [None])[0]
            password = query_params.get("password", [None])[0]
        
        if not self._authorize_token(token):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Invalid token"}')
            return

        try:
            subprocess.run(["docker", "exec", get_web_container(), "rm", "-f", TOKEN_FILE])
        except Exception:
            pass

        with config_lock:
            base_dir = get_base_dir()
            conf_prod = os.path.join(base_dir, "frontend", "default.conf.prod")
            frontend_container = get_frontend_container()

            # 开启时确保或自定义 .htpasswd 凭据
            if enable:
                ensure_htpasswd_file(base_dir, username, password)

            # 1. 获取现有配置内容
            content = None
            target_host_files = []
            if os.path.exists(conf_prod):
                target_host_files.append(conf_prod)
                try:
                    with open(conf_prod, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    pass

            # 若宿主机文件不存在，尝试从容器读取
            if not content:
                try:
                    result = subprocess.run(["docker", "exec", frontend_container, "cat", "/etc/nginx/conf.d/default.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    if result.returncode == 0:
                        content = result.stdout
                except Exception:
                    pass

            if not content:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Unable to locate Nginx configuration file"}')
                return

            # 2. 生成新配置
            original_content = content
            new_content = update_nginx_auth_config(content, enable)

            # 3. 原地重写宿主机配置文件 (保持 Linux Bind Mount 的 inode 一致，容器内部即刻同步生效)
            for host_file in target_host_files:
                try:
                    with open(host_file, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except Exception as e:
                    print(f"[WARN] Failed to write host file {host_file}: {e}", file=sys.stderr)

            # 4. 执行 nginx -t 语法校验
            try:
                test_res = subprocess.run(["docker", "exec", frontend_container, "nginx", "-t"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                if test_res.returncode != 0:
                    # 语法错误，立即原地回滚宿主机文件
                    for host_file in target_host_files:
                        try:
                            with open(host_file, "w", encoding="utf-8") as f:
                                f.write(original_content)
                        except Exception:
                            pass
                    
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    err_msg = f"Nginx 语法测试失败已回滚: {test_res.stderr.strip()}"
                    self.wfile.write(json.dumps({"status": "error", "message": err_msg}).encode('utf-8'))
                    return

                # 5. 语法校验通过，执行热重载
                reload_res = subprocess.run(["docker", "exec", frontend_container, "nginx", "-s", "reload"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                if reload_res.returncode != 0:
                    print(f"[WARN] Nginx reload warning: {reload_res.stderr.strip()}", file=sys.stderr)
                
                # 给予 Nginx worker 进程平滑切换生效的时间 (500ms)
                time.sleep(0.5)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Basic Auth updated successfully", "enabled": enable}).encode('utf-8'))
            except Exception as e:
                # 异常时原地回滚宿主机文件
                for host_file in target_host_files:
                    try:
                        with open(host_file, "w", encoding="utf-8") as f:
                            f.write(original_content)
                    except Exception:
                        pass
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def log_append(self, text):
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(text + "\n")

    def _run_quiet(self, cmd, timeout=None):
        """静默执行命令并返回退出码；命令缺失/超时/执行异常一律视为失败，绝不抛出。"""
        try:
            return subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout
            ).returncode
        except Exception:
            return 1

    def _docker_info_ok(self):
        """探测 Docker 守护进程是否就绪（异常场景返回 False，避免线程静默崩溃）。
        timeout=3 兜底：卡死态 daemon（socket 存在但无响应）会让 docker info 无限阻塞，
        必须显式超时才能让上层自愈链路闭环。"""
        return self._run_quiet(["docker", "info"], timeout=3) == 0

    def _wait_docker_daemon(self, timeout=15):
        """轮询探测 Docker 守护进程就绪（最多 15 轮 × 每轮 ≤3 秒探测，避免慢启动误判）"""
        for _ in range(timeout):
            if self._docker_info_ok():
                return True
            time.sleep(1)
        return False

    def ensure_docker_daemon(self):
        """确保 Docker 守护进程在运行；未运行则尝试启动。返回是否就绪。"""
        if self._docker_info_ok():
            return True

        self.log_append("[WARN] ⚠️ Docker 守护进程未在运行，尝试自动启动...")

        # 方式一：systemd 服务托管
        if shutil.which("systemctl"):
            self._run_quiet(["systemctl", "start", "docker"], timeout=30)
            if self._wait_docker_daemon():
                self.log_append("[INFO] ✅ Docker 守护进程启动成功！")
                return True

        # 方式二：SysV init 服务（仅无 systemd 时使用，避免与托管实例竞争）
        if not shutil.which("systemctl") and shutil.which("service"):
            self._run_quiet(["service", "docker", "start"], timeout=30)
            if self._wait_docker_daemon():
                self.log_append("[INFO] ✅ Docker 守护进程启动成功！")
                return True

        # 兜底：仅在没有 systemd/service 托管的极简环境下直接启动 dockerd
        if not shutil.which("systemctl") and not shutil.which("service") and shutil.which("dockerd"):
            # 防竞争：若已有 dockerd 进程在运行（如 start-prod.sh 刚拉起），直接等待其就绪，
            # 避免两个 dockerd 争抢 /var/run/docker.sock 与 /var/lib/docker 造成数据损坏
            if shutil.which("pgrep") and self._run_quiet(["pgrep", "-x", "dockerd"]) == 0:
                self.log_append("[INFO] 检测到 dockerd 进程已在运行，等待其就绪...")
                if self._wait_docker_daemon():
                    self.log_append("[INFO] ✅ Docker 守护进程已就绪！")
                    return True
                self.log_append("[ERROR] ❌ 已检测到 dockerd 进程但无法就绪，可能存在异常状态，请手动排查。")
                return False
            try:
                # Popen 仅取文件对象 fd 传给子进程，with 块退出关闭父进程副本即可，
                # 子进程持有 dup fd 继续写日志，无句柄泄漏
                with open("/tmp/arl_dockerd.log", "a", encoding="utf-8") as dockerd_log:
                    subprocess.Popen(
                        ["dockerd"],
                        stdout=dockerd_log, stderr=subprocess.STDOUT,
                        # start_new_session=True 等价于 nohup 语义：脱离父进程会话，
                        # 避免 updater 所在终端/会话关闭时 SIGHUP 杀掉 dockerd
                        start_new_session=True
                    )
            except Exception:
                pass
            if self._wait_docker_daemon():
                self.log_append("[INFO] ✅ Docker 守护进程通过 dockerd 直接启动成功！")
                return True

        self.log_append("[ERROR] ❌ Docker 守护进程无法启动，请手动排查：")
        self.log_append("[ERROR]    1. 执行 'journalctl -u docker' 查看日志找出原因")
        self.log_append("[ERROR]    2. 检查 'df -h' 确认磁盘未满")
        self.log_append("[ERROR]    3. 检查 /var/lib/docker 目录权限")
        return False

    def run_update_task(self):
        self.log_append("[INFO] ✅ Token 验证成功，后台任务已启动...")

        # 前置：确保 Docker 守护进程运行，避免把 daemon 未启动误判为网络波动
        if not self.ensure_docker_daemon():
            time.sleep(5)
            return

        script_name = "start-prod.sh"
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", script_name))

        self.log_append("[INFO] 📦 正在拉取核心镜像以提取最新架构配置...")
        image_name = "crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest"
        
        max_retries = 3
        retry_count = 0
        daemon_retry = 0
        max_daemon_retry = 2
        pull_ok = False

        while retry_count < max_retries:
            pull_ok = self.run_command(["docker", "pull", image_name])
            if pull_ok:
                break

            # 区分「Docker 守护进程未运行」与「网络波动」两类失败原因
            if not self._docker_info_ok():
                daemon_retry += 1
                if daemon_retry > max_daemon_retry:
                    self.log_append(f"[ERROR] ❌ Docker 守护进程反复异常，已尝试恢复 {max_daemon_retry} 次仍失败。已中止更新。")
                    time.sleep(5)
                    return
                self.log_append(f"[WARN] ⚠️ Docker 守护进程在拉取中途异常断开，正在尝试自愈恢复 (第 {daemon_retry}/{max_daemon_retry} 次)...")
                if self.ensure_docker_daemon():
                    self.log_append("[INFO] 🔄 Docker 守护进程已成功恢复，正在重新尝试拉取核心镜像...")
                    continue
                else:
                    self.log_append("[ERROR] ❌ Docker 守护进程恢复失败，已中止更新流程。")
                    time.sleep(5)
                    return

            retry_count += 1
            if retry_count >= max_retries:
                self.log_append("[ERROR] ❌ 多次拉取核心镜像失败，请检查服务器网络或稍后重试。已中止更新。")
                time.sleep(5)
                return
            self.log_append(f"[WARN] ⚠️ 核心镜像拉取遇到网络波动，正在进行第 {retry_count} 次重试 (等待 3 秒)...")
            time.sleep(3)

        # 循环唯一出口为 break（pull_ok 恒为 True）或内部 return，此处无需重复兜底

        self.log_append("[INFO] 📦 正在提取并覆盖最新基础架构文件...")
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        copy_cmd = [
            "docker", "run", "--rm",
            "-v", f"{cwd}:/host",
            image_name,
            "bash", "-c",
            """
            cp /code/start-prod.sh /host/start-prod.sh 2>/dev/null || true
            mkdir -p /host/updater && cp /code/updater/updater.py /host/updater/updater.py 2>/dev/null || true
            if [ -f /host/docker-compose.prod.yml ]; then
                cp /host/docker-compose.prod.yml /host/docker-compose.prod.yml.bak_$(date +%Y%m%d%H%M%S) 2>/dev/null || true
            fi
            cp /code/docker-compose.prod.yml /host/docker-compose.prod.yml 2>/dev/null || true
            """
        ]
        self.run_command(copy_cmd)

        # 赋予可执行权限
        subprocess.run(["chmod", "+x", script_path])
        
        self.log_append("[INFO] 📦 基础架构同步完毕，正在拉取其余 Docker 镜像并部署...")
        self.log_append(f"[INFO] 🚀 开始执行 {script_name}，这可能需要几分钟...")
        
        success = self.run_command(["bash", script_path])
        if success:
            self.log_append("[DONE] 🎉 系统更新与部署已全部完成！请刷新页面体验新版本。")
            # 让前端有充足的时间（约5秒）通过轮询获取到最后的 [DONE] 日志
            time.sleep(5)
            
            # 判断是否运行在 systemd 托管下
            is_systemd = False
            try:
                if os.environ.get("INVOCATION_ID") or os.path.exists("/run/systemd/system"):
                    is_systemd = True
            except Exception:
                pass

            if is_systemd:
                os._exit(0)
            else:
                try:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception:
                    os._exit(0)
        else:
            self.log_append("[ERROR] ❌ 部署脚本执行失败，部分服务异常，请仔细检查上述日志！")
            # 失败时保持 Updater 进程存活，避免非 Systemd 环境下进程退出无法重试

    def run_command(self, cmd):
        global dynamic_progress
        import pty
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        env = os.environ.copy()
        env["ARL_UPDATER_SKIP_RESTART"] = "1"
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        master, slave = pty.openpty()
        process = None
        try:
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    close_fds=True,
                    cwd=cwd,
                    env=env
                )
            except Exception:
                # Popen 失败（如 docker 二进制缺失）时回收 slave fd，避免 fd 泄漏
                try:
                    os.close(slave)
                except OSError:
                    pass
                raise
            os.close(slave)
            
            buffer = ""
            while True:
                try:
                    data = os.read(master, 1024).decode('utf-8', errors='ignore')
                    if not data:
                        break
                    
                    data = ansi_escape.sub('', data)
                    buffer += data
                    buffer = buffer.replace('\r\n', '\n').replace('\r', '\n')
                    
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue
                            
                        match = re.search(r'([a-zA-Z0-9_-]+)(?:\s+|:\s+)(Downloading|Extracting|Waiting|Pulling|Already exists|Pull complete|Download complete|Pulled)', line, re.IGNORECASE)
                        if match:
                            layer_id = match.group(1)
                            status_word = match.group(2).lower()
                            
                            # If it's a completion state, remove from dynamic_progress
                            if any(x in status_word for x in ['complete', 'pulled', 'downloaded', 'exists']):
                                if layer_id in dynamic_progress:
                                    del dynamic_progress[layer_id]
                            else:
                                # Not complete, update progress
                                dynamic_progress[layer_id] = line[match.start(2):].strip()
                            continue
                        
                        if any(x in line for x in ['Pulling fs layer', 'Already exists', 'Pull complete', 'Download complete', 'Digest:', 'Status: Downloaded newer image', 'Status: Image is up to date']):
                            continue
                            
                        self.log_append(line)
                except OSError:
                    break
                    
            if process:
                process.wait()
                if process.returncode != 0:
                    self.log_append(f"[ERROR] ⚠️ 脚本执行出错，退出码: {process.returncode}")
                    return False
            return True
        except Exception as e:
            self.log_append(f"[ERROR] ❌ 执行异常: {str(e)}")
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait()
                except Exception:
                    pass
            return False
        finally:
            # 无论成功、失败或发生未捕获异常，始终安全关闭 master fd 并重置动态进度
            try:
                os.close(master)
            except OSError:
                pass
            dynamic_progress.clear()

    def verify_token(self, provided_token):
        if not provided_token:
            return False
        try:
            result = subprocess.run(["docker", "exec", get_web_container(), "cat", TOKEN_FILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if result.returncode == 0:
                valid_token = result.stdout.strip()
                return provided_token == valid_token and len(valid_token) > 10
            else:
                print(f"[WARN] Failed to read token file: {result.stderr.strip()}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Exception during verify_token: {str(e)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), PollingHandler)
    print(f"Update server started on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
