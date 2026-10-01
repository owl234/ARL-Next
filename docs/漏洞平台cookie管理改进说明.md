# Cookie 安全管理改进说明

> **版本**：v1.0
> **日期**：2026-09-30
> **状态**：草案
> **适用范围**：ARL-Next 漏洞平台聚合模块
> **优先级**：P0（紧急）

------

## 一、背景与问题

### 1.1 当前实现

漏洞平台（补天、漏洞盒子、EduSRC 等）的 Cookie 目前**直接硬编码**在 `PLATFORM_CONFIG` 中：

python

```
# backend/app/adapters/vuln_platform/config.py

PLATFORM_CONFIG = {
    "butian": {
        "name": "补天平台",
        "enabled": True,
        "base_url": "https://www.butian.net",
        # ... 其他字段
        "requires_login": True,
        "cookie": "PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; "
                  "__btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099; "
                  "__btc__=652f3272c68f2d04227f1a53dbebbd9988299f7f",
    },
    # ...
}
```



### 1.2 存在的问题

| #    | 问题                    | 严重程度 | 影响                                             |
| :--- | :---------------------- | :------- | :----------------------------------------------- |
| 1    | **敏感信息明文入库**    | 🔴 高     | Cookie 等同于账号密码，一旦提交到 Git 就永久泄露 |
| 2    | **无法多环境切换**      | 🟡 中     | 开发/测试/生产需改代码，容易出错                 |
| 3    | **Cookie 过期需改代码** | 🟡 中     | 重启后新 Cookie 不持久化，需手动改代码再重启     |
| 4    | **无审计追踪**          | 🟡 中     | 谁在什么时候改过 Cookie 无记录                   |
| 5    | **团队成员易误操作**    | 🟠 高     | 复制粘贴到公共仓库、分享到聊天群                 |
| 6    | **无自动刷新机制**      | 🟢 低     | Cookie 过期后需人工介入                          |
| 7    | **违反安全合规**        | 🟠 高     | 等保、ISO 27001 明确禁止硬编码凭证               |

### 1.3 风险场景

text

```
场景 1：开发者本地提交
  开发者 A 修改 config.py → git commit → git push
  → Cookie 进入 Git 历史，永久可查

场景 2：代码审计发现
  审计人员查看源码 → 发现明文 Cookie
  → 合规不通过

场景 3：GitHub 公开仓库
  项目开源 → Cookie 被爬虫抓取
  → 账号被盗用，被平台封号

场景 4：离职员工带走
  员工离职前 git clone → 带走全部 Cookie
  → 无法追溯和撤销
```



------

## 二、改进目标

### 2.1 核心目标

| 目标               | 说明                                 |
| :----------------- | :----------------------------------- |
| **敏感信息零入库** | Cookie 不进入 Git 仓库               |
| **多环境友好**     | 开发/测试/生产用同一份代码，不同配置 |
| **向后兼容**       | 现有调用代码零改动                   |
| **易于运维**       | 支持运行时更新，无需重启             |
| **可审计**         | Cookie 变更记录可追溯                |

### 2.2 非目标

- ❌ 不改动现有 `CookieManager` 接口
- ❌ 不改动适配器、Service、Routes
- ❌ 不引入复杂密钥管理服务（Vault 等）

------

## 三、改进方案

### 3.1 总体设计

采用**三层优先级**的 Cookie 加载策略：

text

```
┌──────────────────────────────────────────────────────────┐
│  优先级 1：环境变量（最高）                                │
│  ├── Docker/K8s 部署首选                                  │
│  ├── 通过 Secret 注入，不落盘                             │
│  └── 例：ARL_COOKIE_BUTIAN="PHPSESSID=xxx; token=yyy"    │
├──────────────────────────────────────────────────────────┤
│  优先级 2：本地配置文件（次之）                            │
│  ├── config_local.py（已加入 .gitignore）                 │
│  ├── 覆盖 PLATFORM_CONFIG 中的 cookie 字段                │
│  └── 适合个人开发环境                                     │
├──────────────────────────────────────────────────────────┤
│  优先级 3：Cookie 文件（兜底）                             │
│  ├── $ARL_COOKIE_DIR/butian.txt                          │
│  ├── 运行时保存最新 Cookie（如自动刷新）                   │
│  └── 适合动态更新场景                                     │
├──────────────────────────────────────────────────────────┤
│  优先级 4：PLATFORM_CONFIG 默认值（最低）                  │
│  ├── 保留空字符串 ""                                      │
│  ├── 仅用于开发调试，不填敏感值                            │
│  └── 生产环境应通过前 3 层覆盖                             │
└──────────────────────────────────────────────────────────┘
```



### 3.2 目录结构

text

```
ARL-Next/backend/app/
├── adapters/vuln_platform/
│   ├── config.py                    # 平台配置（不含敏感 Cookie）
│   ├── config_local.py              # ★ 本地覆盖（.gitignore）
│   ├── config_local.py.example      # ★ 模板（入库）
│   └── cookie_manager.py            # Cookie 管理（不变）
└── tmp/cookies/                     # Cookie 文件目录（.gitignore）
    ├── butian.txt
    ├── vulbox.txt
    └── edusrc.txt
```



------

## 四、实施步骤

### 4.1 第一步：清理敏感信息（1 天）

**目标**：把现有硬编码 Cookie 从代码中移除。

#### 4.1.1 修改 `config.py`

python

```
# backend/app/adapters/vuln_platform/config.py

import os
from app.config import Config


# ═══════════════════════════════════════════════════════════
# Cookie 存储目录
# ═══════════════════════════════════════════════════════════

COOKIE_DIR = os.environ.get(
    "ARL_COOKIE_DIR",
    os.path.join(Config.TMP_PATH, "cookies"),
)
os.makedirs(COOKIE_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 平台配置（Cookie 留空，由外部注入）
# ═══════════════════════════════════════════════════════════

PLATFORM_CONFIG = {
    "butian": {
        "name": "补天平台", "enabled": True,
        "base_url": "https://www.butian.net",
        "login_url": "https://www.butian.net/User/login",
        "test_url": "https://www.butian.net/Rank/company",
        "rate_limit": "6/m", "default_delay": 5.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 12,
        "max_retries": 3, "priority": 8, "requires_login": True,
        "cookie": "",  # ★ 默认空，由 env / config_local / 文件注入
    },
    "vulbox": {
        "name": "漏洞盒子", "enabled": True,
        "base_url": "https://www.vulbox.com",
        "login_url": "https://www.vulbox.com/login",
        "test_url": "https://www.vulbox.com/project",
        "rate_limit": "12/m", "default_delay": 3.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 24,
        "max_retries": 3, "priority": 7, "requires_login": True,
        "cookie": "",
    },
    # ... 其他平台同理
}


# ═══════════════════════════════════════════════════════════
# ★ 加载本地覆盖配置（优先级次高）
# ═══════════════════════════════════════════════════════════

try:
    from .config_local import COOKIE_OVERRIDES
    for platform, cookie in COOKIE_OVERRIDES.items():
        if platform in PLATFORM_CONFIG and cookie:
            PLATFORM_CONFIG[platform]["cookie"] = cookie
except ImportError:
    # config_local.py 不存在时优雅降级
    pass


# ═══════════════════════════════════════════════════════════
# Cookie 工具函数
# ═══════════════════════════════════════════════════════════

def get_cookie_string(platform_name):
    """
    按优先级获取 Cookie 字符串
    优先级：环境变量 > config_local > Cookie 文件 > PLATFORM_CONFIG

    :return: str（浏览器复制的完整 cookie 字符串）或 ""
    """
    cfg = PLATFORM_CONFIG.get(platform_name, {})

    # 1. 环境变量（最高优先级）
    env_key = "ARL_COOKIE_{}".format(platform_name.upper())
    env_value = os.environ.get(env_key, "").strip()
    if env_value:
        return env_value

    # 2. PLATFORM_CONFIG（已被 config_local 覆盖）
    config_value = cfg.get("cookie", "").strip()
    if config_value:
        return config_value

    # 3. Cookie 文件（兜底）
    cookie_file = os.path.join(COOKIE_DIR, "{}.txt".format(platform_name))
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                file_value = f.read().strip()
                if file_value:
                    return file_value
        except Exception:
            pass

    return ""


def get_cookie_ttl(platform_name):
    """获取 Cookie 有效期（小时）"""
    cfg = PLATFORM_CONFIG.get(platform_name, {})
    return cfg.get("cookie_ttl_hours", 12)


def save_cookie_to_file(platform_name, cookie_string):
    """把 Cookie 保存到文件（用于运行时更新）"""
    cookie_file = os.path.join(COOKIE_DIR, "{}.txt".format(platform_name))
    os.makedirs(COOKIE_DIR, exist_ok=True)
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookie_string.strip())


# ═══════════════════════════════════════════════════════════
# 平台配置查询（保持不变）
# ═══════════════════════════════════════════════════════════

def get_platform_config(platform_name):
    """获取平台配置（合并动态覆盖值）"""
    if platform_name not in PLATFORM_CONFIG:
        raise ValueError("未知平台: {}".format(platform_name))

    config = dict(PLATFORM_CONFIG[platform_name])

    if not Config.VULN_PLATFORM_ENABLED:
        config["enabled"] = False

    if platform_name == "hackerone":
        username = Config.HACKERONE_USERNAME
        token = Config.HACKERONE_TOKEN
        if username and token:
            config["enabled"] = True
            config["username"] = username
            config["api_token"] = token

    return config


def get_enabled_platforms():
    """获取所有已启用平台"""
    return [k for k in PLATFORM_CONFIG
            if get_platform_config(k).get("enabled")]
```



#### 4.1.2 创建 `config_local.py.example`

python

```
# backend/app/adapters/vuln_platform/config_local.py.example
"""
本地 Cookie 配置模板
使用方式：
    cp config_local.py.example config_local.py
    编辑 config_local.py 填入真实 Cookie

注意：
    - config_local.py 已加入 .gitignore，不会提交到 Git
    - 仅用于本地开发，生产环境请用环境变量
"""

COOKIE_OVERRIDES = {
    # 从浏览器复制完整 Cookie 字符串
    # "butian": "PHPSESSID=xxx; __btu__=yyy; __btc__=zzz",
    # "vulbox": "PHPSESSID=abc; token=def",
    # "edusrc": "sessionid=xxx; csrftoken=yyy",
}
```



#### 4.1.3 更新 `.gitignore`

gitignore

```
# 敏感配置文件
backend/app/adapters/vuln_platform/config_local.py

# Cookie 存储目录
backend/app/tmp/cookies/

# 其他敏感文件
*.env
.env.local
secrets/
```



#### 4.1.4 清理 Git 历史

**⚠️ 如果 Cookie 已经提交过，必须清理 Git 历史**：

bash

```
# 方法 1：使用 git-filter-repo（推荐）
pip install git-filter-repo
git filter-repo --path backend/app/adapters/vuln_platform/config.py \
    --invert-paths  # 会删除整个文件（谨慎）

# 方法 2：使用 BFG Repo-Cleaner
java -jar bfg.jar --replace-text passwords.txt my-repo.git

# 方法 3：最简单（如仅当前分支）
git rm --cached backend/app/adapters/vuln_platform/config_local.py
git commit --amend
```



**关键**：**清理历史后必须立即更换所有泄露的 Cookie**。

------

### 4.2 第二步：环境变量注入（2 天）

#### 4.2.1 Docker Compose 配置

yaml

```
# docker-compose.yml

services:
  arl-worker-fetch:
    image: arl-worker:latest
    environment:
      # ★ 从宿主机环境变量注入
      - ARL_COOKIE_BUTIAN=${ARL_COOKIE_BUTIAN}
      - ARL_COOKIE_VULBOX=${ARL_COOKIE_VULBOX}
      - ARL_COOKIE_EDUSRC=${ARL_COOKIE_EDUSRC}
      # 或从文件读取
      - ARL_COOKIE_DIR=/run/secrets/cookies
    secrets:
      - cookie_butian
      - cookie_vulbox

secrets:
  cookie_butian:
    file: ./secrets/butian.txt
  cookie_vulbox:
    file: ./secrets/vulbox.txt
```



#### 4.2.2 Kubernetes 配置

yaml

```
# k8s/deployment.yaml

apiVersion: v1
kind: Secret
metadata:
  name: arl-cookies
type: Opaque
stringData:
  ARL_COOKIE_BUTIAN: "PHPSESSID=xxx; __btu__=yyy"
  ARL_COOKIE_VULBOX: "PHPSESSID=abc; token=def"
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: arl-worker
          envFrom:
            - secretRef:
                name: arl-cookies
```



#### 4.2.3 本地开发（.env 文件）

bash

```
# .env（不提交到 Git）

ARL_COOKIE_BUTIAN="PHPSESSID=xxx; __btu__=yyy"
ARL_COOKIE_VULBOX="PHPSESSID=abc; token=def"
```



启动时加载：

bash

```
# 方式 1：source .env
source .env && python -m app.main

# 方式 2：使用 python-dotenv
pip install python-dotenv
```



python

```
# backend/app/main.py（顶部）
from dotenv import load_dotenv
load_dotenv()  # 自动加载 .env
```



------

### 4.3 第三步：文件兜底方案（1 天）

对于**运行时自动刷新**的场景，保留文件存储：

python

```
# cookie_manager.py 改造

class CookieManager:
    def refresh_cookie(self, login_func, *args, **kwargs):
        """刷新 Cookie"""
        try:
            new_cookie = login_func(*args, **kwargs)
            if new_cookie and isinstance(new_cookie, str):
                self.cookie_string = new_cookie
                # ★ 保存到文件（覆盖低优先级来源）
                save_cookie_to_file(self.platform_name, new_cookie)
                return True
            return False
        except Exception as e:
            logger.error("Cookie 刷新失败: {}".format(e))
            return False
```



**注意**：**运行时保存的 Cookie 不会覆盖环境变量**，因为环境变量优先级更高。

------

### 4.4 第四步：审计与监控（3 天）

#### 4.4.1 Cookie 变更审计

python

```
# backend/app/adapters/vuln_platform/cookie_manager.py

def save_cookie_to_file(platform_name, cookie_string):
    """保存 Cookie 并记录审计"""
    # 记录审计日志
    from app.utils.conn import conn_db
    from app.utils.time import utcnow

    conn_db("syslog").insert_one({
        "event": "cookie_update",
        "platform": platform_name,
        "cookie_hash": hashlib.sha256(
            cookie_string.encode()).hexdigest()[:16],
        "cookie_length": len(cookie_string),
        "updated_at": utcnow(),
        # 不记录完整 Cookie！
    })

    # 保存文件
    cookie_file = os.path.join(COOKIE_DIR, "{}.txt".format(platform_name))
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookie_string.strip())
```



#### 4.4.2 Cookie 健康检查

python

```
# tasks/vuln_platform.py

@celery.task(name='app.celerytask.vuln_platform_cookie_check',
             queue='platform_fetch')
def vuln_platform_cookie_check():
    """检查所有平台 Cookie 有效性"""
    from app.adapters.vuln_platform import get_all_adapters

    adapters = get_all_adapters()
    invalid = []
    for name, adapter in adapters.items():
        if not adapter.cookie_mgr:
            continue
        test_url = adapter.config.get("test_url", "")
        if not adapter.cookie_mgr.is_cookie_valid(test_url):
            invalid.append(name)
            logger.warning("[{}] Cookie 已失效".format(name))

    # ★ 失效告警
    if invalid:
        from app.utils.alert import send_alert
        send_alert(
            channel=["dingtalk", "feishu"],
            title="Cookie 失效告警",
            content="以下平台 Cookie 失效：\n{}".format(
                "\n".join("- {}".format(p) for p in invalid)),
            level="warning")
    return {"invalid_cookies": invalid}
```



------

## 五、Cookie 获取与更新流程

### 5.1 手动获取（推荐首次配置）

#### 步骤 1：浏览器登录

访问目标平台（如 [https://www.butian.net](https://www.butian.net/)），完成登录。

#### 步骤 2：F12 打开开发者工具

- **Chrome / Edge**：按 `F12` 或右键 → 检查
- **Firefox**：按 `F12`

#### 步骤 3：切换到 Network 标签

刷新页面（F5），点击任意请求。

#### 步骤 4：复制 Cookie

在 **Headers** → **Request Headers** 中找到 `Cookie:` 字段：

text

```
Cookie: PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; __btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099; __btc__=652f3272c68f2d04227f1a53dbebbd9988299f7f
```



**复制 `Cookie:` 后面的整串内容**。

#### 步骤 5：写入配置

**方式 1：环境变量**

bash

```
export ARL_COOKIE_BUTIAN="PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; __btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099"
```



**方式 2：config_local.py**

python

```
# backend/app/adapters/vuln_platform/config_local.py
COOKIE_OVERRIDES = {
    "butian": "PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; __btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099",
}
```



**方式 3：Cookie 文件**

bash

```
mkdir -p backend/app/tmp/cookies
echo "PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; __btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099" \
    > backend/app/tmp/cookies/butian.txt
```



### 5.2 自动刷新（可选，进阶）

用 Playwright 无头浏览器自动登录并刷新 Cookie：

python

```
# backend/app/adapters/vuln_platform/auto_login.py

from playwright.sync_api import sync_playwright


def auto_login_butian(username, password):
    """
    自动登录补天并获取 Cookie
    :return: Cookie 字符串
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 访问登录页
        page.goto("https://www.butian.net/User/login")

        # 填表单
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)

        # 处理极验滑块（需另做处理）
        # ...

        # 提交
        page.click('button[type="submit"]')
        page.wait_for_url("**/User/**")

        # 获取 Cookie
        cookies = context.cookies()
        cookie_str = "; ".join(
            "{}={}".format(c["name"], c["value"])
            for c in cookies)

        browser.close()
        return cookie_str
```



**集成到 CookieManager**：

python

```
# cookie_manager.py

def auto_refresh_cookie(self):
    """自动刷新 Cookie（如支持）"""
    from .auto_login import auto_login_butian

    if self.platform_name == "butian":
        # 从环境变量读取账号密码
        username = os.environ.get("ARL_BUTIAN_USER")
        password = os.environ.get("ARL_BUTIAN_PASS")
        if not username or not password:
            logger.warning("未配置账号密码，无法自动刷新")
            return False

        new_cookie = auto_login_butian(username, password)
        if new_cookie:
            self.cookie_string = new_cookie
            save_cookie_to_file(self.platform_name, new_cookie)
            return True
    return False
```



------

## 六、验证与测试

### 6.1 验证 Cookie 加载优先级

bash

```
# 1. 清空所有 Cookie 来源
unset ARL_COOKIE_BUTIAN
rm -f backend/app/tmp/cookies/butian.txt

# 2. 修改 config_local.py 加入 Cookie
cat > backend/app/adapters/vuln_platform/config_local.py << 'EOF'
COOKIE_OVERRIDES = {
    "butian": "PHPSESSID=test_local; __btu__=xxx",
}
EOF

# 3. 启动应用
python -c "
from app.adapters.vuln_platform.config import get_cookie_string
print('来自 config_local:', get_cookie_string('butian'))
"

# 4. 设置环境变量后再测试
export ARL_COOKIE_BUTIAN="PHPSESSID=test_env; token=yyy"
python -c "
from app.adapters.vuln_platform.config import get_cookie_string
print('来自 env:', get_cookie_string('butian'))
"
# 应输出 env 的值（优先级更高）
```



### 6.2 验证 Cookie 有效性

python

```
# tests/test_cookie_manager.py
import pytest
from app.adapters.vuln_platform.cookie_manager import CookieManager


def test_cookie_loaded_from_env(monkeypatch):
    monkeypatch.setenv("ARL_COOKIE_BUTIAN", "PHPSESSID=test123")
    mgr = CookieManager("butian")
    assert mgr.cookie_string == "PHPSESSID=test123"


def test_cookie_priority(monkeypatch, tmp_path):
    """环境变量优先于文件"""
    # 创建文件
    cookie_file = tmp_path / "butian.txt"
    cookie_file.write_text("PHPSESSID=from_file")
    monkeypatch.setenv("ARL_COOKIE_BUTIAN", "PHPSESSID=from_env")

    mgr = CookieManager("butian")
    assert mgr.cookie_string == "PHPSESSID=from_env"


def test_cookie_validity_check():
    mgr = CookieManager("butian")
    if not mgr.cookie_string:
        pytest.skip("无 Cookie，跳过")
    # 实际请求测试（需真实 Cookie）
    valid = mgr.is_cookie_valid("https://www.butian.net/Rank/company")
    assert isinstance(valid, bool)
```



### 6.3 验证 Git 敏感信息

bash

```
# 检查是否还有硬编码 Cookie
git grep -i "PHPSESSID\|__btu__\|sessionid=" -- '*.py' '*.yaml' '*.yml'

# 应无输出（或仅出现在 .example 文件）
```



------

## 七、迁移检查清单

### 7.1 迁移前

- □ 

  备份当前 Cookie（导出到安全位置）

- □ 

  确认现有 Cookie 已提交到 Git（如有，需清理历史）

- □ 

  通知团队 Cookie 泄露风险

- □ 

  准备 `.gitignore` 更新

### 7.2 迁移中

- □ 

  修改 `config.py` 清空硬编码 Cookie

- □ 

  创建 `config_local.py.example`

- □ 

  更新 `.gitignore`

- □ 

  实现三层优先级加载逻辑

- □ 

  更新 `cookie_manager.py`

- □ 

  增加审计日志

- □ 

  更新 Docker/K8s 配置

### 7.3 迁移后

- □ 

  验证 Cookie 加载（三种方式）

- □ 

  验证 Cookie 有效性

- □ 

  验证 Cookie 失效告警

- □ 

  清理 Git 历史（如需要）

- □ 

  **更换所有已泄露的 Cookie**（关键！）

- □ 

  更新团队文档

- □ 

  加入监控告警

------

## 八、监控与告警

### 8.1 关键指标

| 指标                    | 阈值     | 告警方式    |
| :---------------------- | :------- | :---------- |
| **Cookie 失效平台数**   | > 0      | 钉钉 + 邮件 |
| **Cookie 加载失败次数** | > 3/小时 | 邮件        |
| **Cookie 有效期剩余**   | < 2 小时 | 钉钉        |
| **Cookie 刷新失败率**   | > 50%    | 钉钉 + 电话 |

### 8.2 定时任务配置

python

```
# celerytask.py 的 beat_schedule

celery.conf.beat_schedule.update({
    "cookie-health-check": {
        "task": "app.celerytask.vuln_platform_cookie_check",
        "schedule": crontab(minute="*/30"),  # 每 30 分钟
    },
    "cookie-expiry-warning": {
        "task": "app.celerytask.cookie_expiry_warning",
        "schedule": crontab(hour="*/6"),  # 每 6 小时
    },
})
```



------

## 九、附录

### 9.1 Cookie 提取命令（一键）

bash

```
#!/bin/bash
# scripts/extract_cookie.sh
# 用法：./extract_cookie.sh butian

PLATFORM=$1
ENV_KEY="ARL_COOKIE_${PLATFORM^^}"

echo "请在浏览器中登录 $PLATFORM 平台"
echo "1. F12 → Network → 刷新页面"
echo "2. 点击任意请求 → Headers → Request Headers"
echo "3. 复制 Cookie: 后面的整串内容"
echo ""
read -p "粘贴 Cookie: " cookie_value

# 写入环境变量（当前会话）
export $ENV_KEY="$cookie_value"
echo "已设置环境变量：$ENV_KEY"
echo "如需持久化，请加入 ~/.bashrc 或 .env 文件"
```



### 9.2 常见问题

**Q1：Cookie 设置后仍然提示未登录？**

- 检查 Cookie 字符串是否完整（以 `;` 分隔）
- 检查环境变量名是否正确（大小写敏感）
- 检查平台是否需要 User-Agent 匹配

**Q2：如何知道 Cookie 是否过期？**

python

```
from app.adapters.vuln_platform.cookie_manager import CookieManager

mgr = CookieManager("butian")
print("有效:" , mgr.is_cookie_valid("https://www.butian.net/Rank/company"))
```



**Q3：Cookie 泄露后如何处理？**

1. **立即登录平台修改密码**（使旧 Cookie 失效）
2. **清理 Git 历史**（`git filter-repo`）
3. **通知团队**（如 Cookie 已被克隆）
4. **加强监控**（检查是否有异常登录）

**Q4：是否可以用 Cookie 长期运行？**

不建议。原因：

- Cookie 有时效性（通常 7-30 天）
- 平台可能主动失效（异地登录、风控）
- 建议配合**自动刷新**或**定期人工更新**

------

## 十、总结

| 维度            | 改进前             | 改进后                         |
| :-------------- | :----------------- | :----------------------------- |
| **Cookie 存储** | 硬编码在 config.py | 环境变量 / config_local / 文件 |
| **Git 安全性**  | 🔴 会泄露           | ✅ 不进入仓库                   |
| **多环境**      | 需改代码           | ✅ 配置驱动                     |
| **运行时更新**  | 需重启             | ✅ 文件保存 + 动态加载          |
| **审计追踪**    | 无                 | ✅ syslog 记录                  |
| **失效告警**    | 无                 | ✅ 定时检查 + 多渠道通知        |
| **团队协作**    | 高风险             | ✅ 每人本地配置，互不影响       |

**核心原则**：

> **代码与配置分离，配置与密钥分离。**
>
> 代码入库，配置本地，密钥环境注入。

**建议实施顺序**：

1. **第 1 天**：清理硬编码，加入 .gitignore
2. **第 2-3 天**：实现三层优先级加载
3. **第 4-5 天**：环境变量 + Docker 配置
4. **第 6-7 天**：审计日志 + 失效告警
5. **第 8 天后**：监控、文档、团队培训

**一周内可完成 P0 级别改进**，风险立竿见影地降低。