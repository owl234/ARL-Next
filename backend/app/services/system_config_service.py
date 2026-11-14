import os
import re
import time
import requests

_UPDATE_CACHE = {
    "timestamp": 0,
    "data": None
}


def _credential_presence():
    """列出各三方凭据的配置状态，供前端渲染状态徽章。

    只返回布尔值与"是否来自 config.yaml 默认"标记，避免凭据经 GET 泄漏。
    """
    from app.config import Config
    from app.utils.conn import conn_db

    doc = conn_db('system_config').find_one({"_id": "general_config"}) or {}

    fields = {
        "fofa_key": ("FOFA_KEY", "fofa_key"),
        "github_token": ("GITHUB_TOKEN", "github_token"),
        "tyc_id": ("TYC_ID", "tyc_id"),
        "tyc_token": ("TYC_TOKEN", "tyc_token"),
        "so_search_cookie": ("SO_SEARCH_COOKIE", "so_search_cookie"),
        "bing_search_cookie": ("BING_SEARCH_COOKIE", "bing_search_cookie"),
        "api_key": ("API_KEY", "api_key"),
        "webhook_token": ("WEB_HOOK_TOKEN", "webhook_token"),
        "dingding_access_token": ("DINGDING_ACCESS_TOKEN", "dingding_access_token"),
        "feishu_webhook": ("FEISHU_WEBHOOK", "feishu_webhook"),
        "wx_work_webhook": ("WX_WORK_WEBHOOK", "wx_work_webhook"),
        "tg_bot_token": ("TG_BOT_TOKEN", "tg_bot_token"),
        "email_username": ("EMAIL_USERNAME", "email_username"),
    }

    result = {}
    for label, (attr_name, db_key) in fields.items():
        try:
            value = getattr(Config, attr_name, "") or ""
        except Exception:
            value = ""
        configured = bool(str(value).strip())
        result[label] = {
            "configured": configured,
            "from_db": db_key in doc,
        }
    return result


def _security_policy_source():
    """返回安全策略当前生效值及其来源，供前端回显。

    显式区分 database / config_yaml 两种来源。
    """
    from app.config import Config
    from app.utils.conn import conn_db

    doc = conn_db('system_config').find_one({"_id": "security_policy"})
    if doc:
        return {
            "source": "database",
            "black_ips": doc.get("black_ips", []),
            "forbidden_domains": doc.get("forbidden_domains", []),
        }
    return {
        "source": "config_yaml",
        "black_ips": list(getattr(Config, "BLACK_IPS", []) or []),
        "forbidden_domains": list(getattr(Config, "FORBIDDEN_DOMAINS", []) or []),
    }


def dispatch_test_push(push_type: str, config: dict) -> dict:
    """执行单通道消息推送连通性测试"""
    from app.utils.push import dingding_send, feishu_send, wx_work_send, send_email, telegram_send
    from app.utils import http_req

    test_msg = "*【ARL-Next 系统通知】这是一条测试消息，您的推送配置一切正常。*"
    test_html = "<div><b>【ARL-Next 系统通知】</b>这是一条测试消息，您的推送配置一切正常。</div>"

    try:
        if push_type == "dingding":
            access_token = config.get("access_token")
            secret = config.get("secret")
            if not access_token or not secret:
                return {"code": 400, "message": "钉钉测试失败：Token 或 Secret 不能为空"}
            res = dingding_send(msg=test_msg, access_token=access_token, secret=secret, msgtype="markdown")
            if res.get("errcode") != 0:
                return {"code": 500, "message": f"钉钉推送失败: {res}"}
            return {"code": 200, "message": "钉钉测试推送成功"}

        elif push_type == "feishu":
            webhook_url = config.get("webhook_url")
            secret = config.get("secret")
            if not webhook_url or not secret:
                return {"code": 400, "message": "飞书测试失败：Webhook URL 或 Secret 不能为空"}
            res = feishu_send(msg=test_msg, webhook_url=webhook_url, secret=secret)
            if res.get("code") != 0:
                return {"code": 500, "message": f"飞书推送失败: {res}"}
            return {"code": 200, "message": "飞书测试推送成功"}

        elif push_type == "wxwork":
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                return {"code": 400, "message": "企业微信测试失败：Webhook URL 不能为空"}
            res = wx_work_send(msg=test_msg, webhook_url=webhook_url)
            if res.get("errcode") != 0:
                return {"code": 500, "message": f"企业微信推送失败: {res}"}
            return {"code": 200, "message": "企业微信测试推送成功"}

        elif push_type == "telegram":
            bot_token = config.get("bot_token")
            chat_id = config.get("chat_id")
            if not bot_token or not chat_id:
                return {"code": 400, "message": "Telegram 测试失败：Bot Token 或 Chat ID 不能为空"}
            res = telegram_send(msg=test_msg, bot_token=bot_token, chat_id=chat_id)
            if not res.get("ok"):
                return {"code": 500, "message": f"Telegram 推送失败: {res}"}
            return {"code": 200, "message": "Telegram 测试推送成功"}

        elif push_type == "email":
            host = config.get("host")
            port = config.get("port")
            username = config.get("username")
            password = config.get("password")
            to = config.get("to")
            if not all([host, port, username, password, to]):
                return {"code": 400, "message": "邮件测试失败：所有邮件配置字段均不能为空"}
            try:
                port = int(port)
            except ValueError:
                return {"code": 400, "message": "邮件测试失败：端口必须为数字"}

            send_email(host=host, port=port, mail=username, password=password, to=to, title="[ARL-Next] 邮件测试推送", html=test_html)
            return {"code": 200, "message": "邮件测试推送成功"}

        elif push_type == "webhook":
            webhook_url = config.get("webhook_url")
            webhook_token = config.get("webhook_token")
            if not webhook_url:
                return {"code": 400, "message": "Webhook 测试失败：回调 URL 不能为空"}

            headers = {}
            if webhook_token:
                headers["Token"] = webhook_token

            payload = {
                "type": "test_push",
                "message": "这是一条 ARL-Next 系统的 Webhook 测试数据",
                "timestamp": time.time()
            }
            conn = http_req(webhook_url, method='post', json=payload, headers=headers, timeout=10)
            if conn.status_code >= 400:
                return {"code": 500, "message": f"Webhook 请求失败，状态码: {conn.status_code}, 响应: {conn.text[:200]}"}
            return {"code": 200, "message": "Webhook 测试回调成功"}

        else:
            return {"code": 400, "message": "不支持的测试推送类型"}

    except Exception as e:
        return {"code": 500, "message": f"测试推送过程中发生异常: {str(e)}"}


def get_local_version_str() -> str:
    """读取本地版本号"""
    candidates = [
        '/code/version.txt',
        'version.txt',
        os.path.join(os.path.dirname(__file__), '../../../version.txt')
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
    return '未知版本'


_GITHUB_REPO_URL = "https://github.com/owl234/ARL-Next"
_GITHUB_API_BASE = "https://api.github.com/repos/owl234/ARL-Next"
_GITHUB_RAW_BASE = "https://raw.githubusercontent.com/owl234/ARL-Next"
_UPDATE_CACHE_DOC_ID = "update_check_cache"
_UPDATE_CACHE_TTL_FULL = 3600
_UPDATE_CACHE_TTL_DEGRADED = 60


def _is_zh_locale(lang: str) -> bool:
    return str(lang or "zh-CN").strip().lower().startswith("zh")


def _github_proxies():
    """读取系统配置中的出站代理地址，与 http_req 保持一致。"""
    try:
        from app.config import Config
        proxy_url = str(getattr(Config, "PROXY_URL", "") or "").strip()
        if proxy_url:
            return {"http": proxy_url, "https": proxy_url}
    except Exception:
        pass
    return None


def _github_get(url: str, headers: dict = None, timeout: int = 8):
    kwargs = {"headers": headers or {}, "timeout": timeout}
    proxies = _github_proxies()
    if proxies:
        kwargs["proxies"] = proxies
    return requests.get(url, **kwargs)


def extract_changelog_section(content: str, tag: str) -> str:
    """从 CHANGELOG Markdown 全文中提取指定版本章节正文。"""
    if not content or not tag or tag == '未知版本':
        return ''
    core = re.escape(tag.strip().lstrip('vV'))
    if not core:
        return ''
    pattern = rf'^##\s*\[?v?{core}\]?(?=\s|\]|$).*?\r?\n(.*?)(?=\r?\n##\s*\[?(?:v|\d)|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not match:
        return ''
    notes = match.group(1).strip()
    return re.sub(r'\r?\n---+\s*$', '', notes).strip()


def _read_local_changelog_section(tag: str, filename: str) -> str:
    candidates = [
        f'/code/{filename}',
        filename,
        os.path.join(os.path.dirname(__file__), f'../../../{filename}')
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    section = extract_changelog_section(f.read(), tag)
                    if section:
                        return section
            except Exception:
                pass
    return ''


def get_local_changelog_section(tag: str, lang: str = 'zh-CN') -> str:
    """从本地 CHANGELOG 文件中提取指定版本的更新说明（按界面语言优先并自动回退）。"""
    filenames = ('CHANGELOG.md', 'CHANGELOG_en.md') if _is_zh_locale(lang) else ('CHANGELOG_en.md', 'CHANGELOG.md')
    for filename in filenames:
        section = _read_local_changelog_section(tag, filename)
        if section:
            return section
    return ''


def is_version_greater(v1: str, v2: str) -> bool:
    """比较版本号 v1 是否大于 v2 (支持 v1.2.0-fix1 等格式)"""
    if not v1 or not v2 or v1 == '未知版本' or v2 == '未知版本':
        return False

    clean1 = v1.lstrip('v').strip()
    clean2 = v2.lstrip('v').strip()

    base1, *suffix1 = clean1.split('-', 1)
    base2, *suffix2 = clean2.split('-', 1)

    parts1 = [int(x) for x in re.findall(r'\d+', base1)]
    parts2 = [int(x) for x in re.findall(r'\d+', base2)]

    for i in range(max(len(parts1), len(parts2))):
        n1 = parts1[i] if i < len(parts1) else 0
        n2 = parts2[i] if i < len(parts2) else 0
        if n1 > n2:
            return True
        if n1 < n2:
            return False

    s1 = suffix1[0] if suffix1 else ''
    s2 = suffix2[0] if suffix2 else ''

    if s1 and not s2:
        return True
    if not s1 and s2:
        return False
    if s1 and s2:
        nums1 = [int(x) for x in re.findall(r'\d+', s1)]
        nums2 = [int(x) for x in re.findall(r'\d+', s2)]
        num1 = nums1[0] if nums1 else 0
        num2 = nums2[0] if nums2 else 0
        if num1 != num2:
            return num1 > num2
        return s1 > s2
    return False


def _pick_highest_tag(tags: list) -> str:
    valid_tags = [
        str(t.get("name")).strip()
        for t in (tags or [])
        if isinstance(t, dict)
        and t.get("name")
        and re.match(r'^v?\d+(?:\.\d+)*', str(t.get("name")).strip(), re.IGNORECASE)
    ]
    if not valid_tags:
        return ""
    best = valid_tags[0]
    for candidate in valid_tags[1:]:
        if is_version_greater(candidate, best):
            best = candidate
    return best


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))


def _split_release_notes(body: str) -> tuple:
    """拆分 GitHub Release 双语正文为 (zh, en, raw)。"""
    raw = (body or '').strip()
    if not raw:
        return '', '', ''
    parts = re.split(r'\r?\n\s*---+\s*\r?\n', raw, maxsplit=1)
    if len(parts) == 2:
        first, second = parts[0].strip(), parts[1].strip()
        if _contains_cjk(first) and not _contains_cjk(second):
            return first, second, raw
        if _contains_cjk(second) and not _contains_cjk(first):
            return second, first, raw
    if _contains_cjk(raw):
        return raw, '', raw
    return '', raw, raw


def _select_release_notes(notes_zh: str, notes_en: str, notes_raw: str, lang: str = 'zh-CN') -> str:
    if _is_zh_locale(lang):
        return (notes_zh or notes_raw or notes_en or '').strip()
    return (notes_en or notes_raw or notes_zh or '').strip()


def _fetch_remote_release(url: str, headers: dict) -> tuple:
    try:
        resp = _github_get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            rel_data = resp.json() or {}
            return (
                (rel_data.get("tag_name") or "").strip(),
                (rel_data.get("body") or "").strip(),
                rel_data.get("html_url") or "",
                rel_data.get("published_at") or "",
            )
    except Exception:
        pass
    return "", "", "", ""


def _fetch_remote_changelog_notes(tag: str, headers: dict) -> tuple:
    """当 Release 正文缺失或与 Tag 存在发布时间差时，直接从远端 Tag 树读取 CHANGELOG。"""
    if not tag or tag == '未知版本':
        return "", ""
    notes_zh = ""
    notes_en = ""
    for filename, is_zh in (("CHANGELOG.md", True), ("CHANGELOG_en.md", False)):
        try:
            resp = _github_get(f"{_GITHUB_RAW_BASE}/{tag}/{filename}", headers=headers, timeout=8)
            if resp.status_code == 200 and resp.text:
                section = extract_changelog_section(resp.text, tag)
                if is_zh:
                    notes_zh = section
                else:
                    notes_en = section
        except Exception:
            pass
    return notes_zh, notes_en


def _read_shared_update_cache():
    """读取跨 Worker 共享缓存（MongoDB system_config），不可用时回退进程内存。"""
    try:
        from app.utils.conn import conn_db
        doc = conn_db('system_config').find_one({"_id": _UPDATE_CACHE_DOC_ID})
        if doc and isinstance(doc.get("data"), dict):
            return float(doc.get("timestamp") or 0), doc["data"]
    except Exception:
        pass
    return float(_UPDATE_CACHE.get("timestamp") or 0), _UPDATE_CACHE.get("data")


def _write_shared_update_cache(now: float, cache_payload: dict):
    _UPDATE_CACHE["timestamp"] = now
    _UPDATE_CACHE["data"] = cache_payload
    try:
        from app.utils.conn import conn_db
        conn_db('system_config').update_one(
            {"_id": _UPDATE_CACHE_DOC_ID},
            {"$set": {"timestamp": now, "data": cache_payload}},
            upsert=True
        )
    except Exception:
        pass


def _build_update_response(entry: dict, local_v: str, lang: str = 'zh-CN', is_cached: bool = False) -> dict:
    remote_v = entry.get("remote_version") or local_v
    is_offline = bool(entry.get("is_offline", False))
    notes_zh = entry.get("release_notes_zh") or ""
    notes_en = entry.get("release_notes_en") or ""
    notes_raw = entry.get("release_notes_raw") or ""

    if is_offline and local_v and local_v != '未知版本':
        remote_v = local_v

    if remote_v == local_v and local_v != '未知版本':
        if not notes_zh:
            notes_zh = _read_local_changelog_section(local_v, 'CHANGELOG.md')
        if not notes_en:
            notes_en = _read_local_changelog_section(local_v, 'CHANGELOG_en.md')
        if not notes_raw:
            notes_raw = notes_zh or notes_en

    selected_notes = _select_release_notes(notes_zh, notes_en, notes_raw, lang=lang)
    has_new = is_version_greater(remote_v, local_v)

    return {
        "local_version": local_v,
        "remote_version": remote_v,
        "has_new_version": has_new,
        "release_notes": selected_notes,
        "html_url": entry.get("html_url") or _GITHUB_REPO_URL,
        "published_at": entry.get("published_at") or "",
        "is_cached": is_cached,
        "is_offline": is_offline,
        "notes_unavailable": bool(has_new and not selected_notes.strip()),
    }


def check_system_update_info(force_refresh: bool = False, lang: str = 'zh-CN') -> dict:
    """检查系统版本更新与获取更新日志（支持代理、远端回退与跨 Worker 共享缓存）"""
    local_v = get_local_version_str()
    now = time.time()

    if not force_refresh:
        cached_ts, cached_entry = _read_shared_update_cache()
        if isinstance(cached_entry, dict):
            cached_remote = cached_entry.get("remote_version") or ""
            # 若本地容器已升级到高于缓存远端版本的新包，立即穿透旧缓存
            if not is_version_greater(local_v, cached_remote):
                ttl = _UPDATE_CACHE_TTL_DEGRADED if cached_entry.get("is_degraded") else _UPDATE_CACHE_TTL_FULL
                if cached_ts <= now + 60 and (now - cached_ts < ttl):
                    _UPDATE_CACHE["timestamp"] = cached_ts
                    _UPDATE_CACHE["data"] = cached_entry
                    return _build_update_response(cached_entry, local_v=local_v, lang=lang, is_cached=True)

    html_url = _GITHUB_REPO_URL
    is_offline = False

    headers = {
        "User-Agent": "ARL-Next-Server",
        "Accept": "application/vnd.github.v3+json"
    }

    remote_v, raw_body, rel_html_url, published_at = _fetch_remote_release(
        f"{_GITHUB_API_BASE}/releases/latest", headers
    )
    if rel_html_url:
        html_url = rel_html_url

    if not remote_v:
        try:
            tag_resp = _github_get(f"{_GITHUB_API_BASE}/tags?per_page=20", headers=headers, timeout=8)
            if tag_resp.status_code == 200:
                tags = tag_resp.json()
                if isinstance(tags, list):
                    remote_v = _pick_highest_tag(tags)
        except Exception:
            pass

        if remote_v:
            _, tag_body, tag_html_url, tag_published_at = _fetch_remote_release(
                f"{_GITHUB_API_BASE}/releases/tags/{remote_v}", headers
            )
            if tag_body:
                raw_body = tag_body
            if tag_html_url:
                html_url = tag_html_url
            else:
                html_url = f"{_GITHUB_REPO_URL}/releases"
            if tag_published_at:
                published_at = tag_published_at

    notes_zh, notes_en, notes_raw = _split_release_notes(raw_body)

    if remote_v and not (notes_zh or notes_en or notes_raw):
        raw_zh, raw_en = _fetch_remote_changelog_notes(remote_v, headers)
        if raw_zh or raw_en:
            notes_zh = raw_zh
            notes_en = raw_en
            notes_raw = raw_zh or raw_en

    if not remote_v:
        remote_v = local_v
        is_offline = True

    if remote_v == local_v and local_v != '未知版本':
        if not notes_zh:
            notes_zh = _read_local_changelog_section(local_v, 'CHANGELOG.md')
        if not notes_en:
            notes_en = _read_local_changelog_section(local_v, 'CHANGELOG_en.md')
        if not notes_raw:
            notes_raw = notes_zh or notes_en

    has_any_notes = bool((notes_zh or notes_en or notes_raw).strip())
    cache_payload = {
        "remote_version": remote_v,
        "release_notes_zh": notes_zh,
        "release_notes_en": notes_en,
        "release_notes_raw": notes_raw,
        "html_url": html_url,
        "published_at": published_at,
        "is_offline": is_offline,
        "is_degraded": bool(is_offline or not has_any_notes),
    }

    _write_shared_update_cache(now, cache_payload)
    return _build_update_response(cache_payload, local_v=local_v, lang=lang, is_cached=False)
