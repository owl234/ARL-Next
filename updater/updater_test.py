import os
import sys
import json
import time
import subprocess
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

TOKEN_FILE = "/tmp/arl_update_token"
LOG_FILE = "/tmp/arl_update.log"
PORT = 8889

update_thread = None
dynamic_progress = {}

class PollingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        # 仅允许本地或 Docker 内部局域网网段访问，拦截公网裸奔请求
        client_ip = self.client_address[0]
        if not (client_ip.startswith("172.") or client_ip.startswith("192.168.") or client_ip.startswith("10.") or client_ip == "127.0.0.1"):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Forbidden: External IP access denied')
            return

        if parsed_url.path == "/update/trigger":
            self.handle_trigger(parsed_url)
        elif parsed_url.path == "/update/log":
            self.handle_log()
        elif parsed_url.path == "/update/auth_status":
            self.handle_auth_status()
        elif parsed_url.path == "/update/toggle_auth":
            self.handle_toggle_auth(parsed_url)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_trigger(self, parsed_url):
        global update_thread, dynamic_progress
        query_params = parse_qs(parsed_url.query)
        token = query_params.get("token", [""])[0]
        
        if not self.verify_token(token):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Invalid token"}')
            return

        # Invalidate token inside container
        try:
            subprocess.run(["docker", "exec", "arl-web-test", "rm", "-f", TOKEN_FILE])
        except Exception:
            pass

        # clear log file
        with open(LOG_FILE, 'w') as f:
            f.write("⏳ 正在初始化更新任务...\n")
        
        dynamic_progress.clear()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "message": "Update triggered"}')

        # Start update in background if not already running
        if update_thread is None or not update_thread.is_alive():
            update_thread = threading.Thread(target=self.run_update_task)
            update_thread.start()

    def handle_log(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
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
        try:
            result = subprocess.run(["docker", "exec", "arl-frontend-test", "cat", "/etc/nginx/conf.d/default.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                content = result.stdout
                if "auth_basic off;" in content:
                    enabled = False
        except Exception:
            pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "enabled": enabled}).encode('utf-8'))

    def handle_toggle_auth(self, parsed_url):
        query_params = parse_qs(parsed_url.query)
        token = query_params.get("token", [""])[0]
        enable = query_params.get("enable", ["true"])[0].lower() == "true"
        
        if not self.verify_token(token):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Invalid token"}')
            return

        try:
            subprocess.run(["docker", "exec", "arl-web-test", "rm", "-f", TOKEN_FILE])
        except Exception:
            pass

        try:
            result = subprocess.run(["docker", "exec", "arl-frontend-test", "cat", "/etc/nginx/conf.d/default.conf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                content = result.stdout
                if enable:
                    content = re.sub(r'auth_basic\s+off;', 'auth_basic "Restricted Access - AntiScan";', content)
                else:
                    content = re.sub(r'auth_basic\s+"Restricted Access - AntiScan";', 'auth_basic off;', content)
                
                import uuid
                # Write back to container
                temp_conf = f"/tmp/arl_nginx_default_{uuid.uuid4().hex}.conf"
                with open(temp_conf, "w", encoding="utf-8") as f:
                    f.write(content)
                subprocess.run(["docker", "cp", temp_conf, "arl-frontend-test:/etc/nginx/conf.d/default.conf"])
                os.remove(temp_conf)
                
                # Reload Nginx
                subprocess.run(["docker", "exec", "arl-frontend-test", "nginx", "-s", "reload"], check=False)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Basic Auth updated successfully", "enabled": enable}).encode('utf-8'))
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Failed to read nginx config from container"}')
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def log_append(self, text):
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(text + "\n")

    def run_update_task(self):
        self.log_append("[INFO] ✅ Token 验证成功，后台任务已启动...")
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "start-test.sh"))
        
        self.log_append("[INFO] 📦 正在拉取核心镜像以提取最新架构配置...")
        image_name = "crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod-test/arl-web:latest"
        if not self.run_command(["docker", "pull", image_name]):
            self.log_append("[ERROR] ❌ 核心镜像拉取失败，可能是网络波动。已中止更新流程，请稍后重试。")
            time.sleep(5)
            return
        
        self.log_append("[INFO] 📦 正在提取并覆盖最新基础架构文件...")
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        copy_cmd = [
            "docker", "run", "--rm",
            "-v", f"{cwd}:/host",
            image_name,
            "bash", "-c",
            "cp /code/start-test.sh /code/docker-compose.test.yml /host/ 2>/dev/null || true; mkdir -p /host/updater && cp /code/updater/updater_test.py /host/updater/ 2>/dev/null || true"
        ]
        self.run_command(copy_cmd)
        
        # 赋予可执行权限
        subprocess.run(["chmod", "+x", script_path])
        
        self.log_append("[INFO] 📦 基础架构同步完毕，正在拉取其余 Docker 镜像并部署...")
        self.log_append("[INFO] 🚀 开始执行 start-test.sh，这可能需要几分钟...")
        
        success = self.run_command(["bash", script_path])
        if success:
            self.log_append("[DONE] 🎉 系统更新与部署已全部完成！请刷新页面体验新版本。")
        else:
            self.log_append("[ERROR] ❌ 部署脚本执行失败，部分服务异常，请仔细检查上述日志！")
            
        # 让前端有充足的时间（约5秒）通过轮询获取到最后的 [DONE] 或 [ERROR] 日志
        time.sleep(5)
        # 体面地结束整个 Python 进程，触发 Systemd 的 Restart=always 机制拉起新版本
        os._exit(0)

    def run_command(self, cmd):
        global dynamic_progress
        import pty
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        try:
            env = os.environ.copy()
            env["ARL_UPDATER_SKIP_RESTART"] = "1"
            cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
            master, slave = pty.openpty()
            process = subprocess.Popen(
                cmd,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
                cwd=cwd,
                env=env
            )
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
                    
            process.wait()
            dynamic_progress.clear()
            
            if process.returncode != 0:
                self.log_append(f"[ERROR] ⚠️ 脚本执行出错，退出码: {process.returncode}")
                return False
            return True
        except Exception as e:
            self.log_append(f"[ERROR] ❌ 执行异常: {str(e)}")
            return False

    def verify_token(self, provided_token):
        if not provided_token:
            return False
        try:
            result = subprocess.run(["docker", "exec", "arl-web-test", "cat", TOKEN_FILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                valid_token = result.stdout.strip()
                return provided_token == valid_token and len(valid_token) > 10
        except Exception:
            pass
        return False

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), PollingHandler)
    print(f"Update server started on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
