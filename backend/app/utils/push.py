import re
import html as html_lib
import time
import base64
import hmac
import urllib.parse
import hashlib
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.utils import http_req, get_logger
from app.config import Config

logger = get_logger()


def strip_markdown_syntax(text: str) -> str:
    """
    清洗文本中的 Markdown 标记，转为高可读性纯文本
    彻底避免在不支持 Markdown 语法的推送通道（如飞书、企业微信等）出现标记乱码
    """
    if not text:
        return ""
    # 1. 转换超链接 [title](url) -> title (url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    # 2. 移除行首标题符 #, ##, ### 等
    text = re.sub(r'^[ \t]*#{1,6}[ \t]*', '', text, flags=re.MULTILINE)
    # 3. 移除粗体/斜体 **text**, *text*, __text__, _text_
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # 4. 移除行内代码 `code`
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 5. 移除引用符号 >
    text = re.sub(r'^[ \t]*>[ \t]*', '', text, flags=re.MULTILINE)
    # 6. 表格分隔线清理（如 | :--- | :---: |）
    text = re.sub(r'^[ \t]*\|[ \t]*:?[-]+:?[ \t]*\|.*$', '', text, flags=re.MULTILINE)
    # 7. 分隔线规范化
    text = re.sub(r'^[ \t]*-{3,}[ \t]*$', '-----------------------------', text, flags=re.MULTILINE)
    # 8. 连续多个空行压缩为一个
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


CATEGORY_LABELS = {
    "site": "Web 站点",
    "domain": "域名资产",
    "ip": "IP 地址",
    "service": "开放端口服务",
    "vuln": "应用系统漏洞",
    "nuclei_result": "Nuclei 漏洞",
    "fileleak": "敏感文件泄露",
    "wih": "Web 信息泄露",
    "url": "抓取 URL",
    "cert": "SSL/TLS 证书",
    "npoc_service": "PoC 关联服务",
    "cip": "C段资产",
    "stat_finger": "命中指纹",
}

CATEGORY_ORDER = [
    "site", "domain", "ip", "service", "vuln", "nuclei_result",
    "fileleak", "wih", "url", "cert", "npoc_service", "cip", "stat_finger"
]


class Push(object):
    """
    资产任务完成消息推送（消息概要模式）
    汇总统计各类资产变动，针对各推送平台自适应排版
    """

    def __init__(self, asset_map, asset_counter, update_map=None, update_counter=None):
        super(Push, self).__init__()
        self.asset_map = asset_map or {}
        self.asset_counter = asset_counter or {}
        self.update_map = update_map or {}
        self.update_counter = update_counter or {}
        self.task_name = self.asset_map.get("task_name", "")
        self.has_any_data = any(v > 0 for v in self.asset_counter.values()) or any(v > 0 for v in self.update_counter.values())

    def _get_summary_data(self):
        """
        汇总各资产分类的新增与更新数量
        返回: (summary_rows, total_new, total_update, has_vuln)
        """
        all_cats = set(self.asset_counter.keys()) | set(self.update_counter.keys())
        ordered_cats = [c for c in CATEGORY_ORDER if c in all_cats] + sorted([c for c in all_cats if c not in CATEGORY_ORDER])

        summary_rows = []
        total_new = 0
        total_update = 0
        has_vuln = False

        for cat in ordered_cats:
            c_new = int(self.asset_counter.get(cat, 0))
            c_update = int(self.update_counter.get(cat, 0))
            if c_new > 0 or c_update > 0:
                label = CATEGORY_LABELS.get(cat, cat)
                summary_rows.append({
                    "key": cat,
                    "label": label,
                    "new": c_new,
                    "update": c_update
                })
                total_new += c_new
                total_update += c_update
                if cat in ("vuln", "nuclei_result") and (c_new > 0 or c_update > 0):
                    has_vuln = True

        return summary_rows, total_new, total_update, has_vuln

    def _generate_plain_text_payload(self):
        """
        适用于各 IM 平台（飞书、钉钉、企微、Telegram 等）的优美结构化纯文本排版
        彻底不添加任何 Markdown 语法标记
        """
        if not self.has_any_data:
            return (
                f"【ARL-Next 任务完成通知】\n"
                f"任务名称：{self.task_name}\n\n"
                f"任务已执行完毕，本次未发现新增或变动资产。"
            )

        rows, total_new, total_update, has_vuln = self._get_summary_data()

        lines = [
            "【ARL-Next 任务完成通知】",
            f"任务名称：{self.task_name}",
            "",
            "【资产变动汇总】",
            f"🌟 新增资产总计：{total_new} 项",
            f"🔄 更新资产总计：{total_update} 项",
            "-----------------------------"
        ]

        for r in rows:
            lines.append(f"• {r['label']}：新增 {r['new']}，更新 {r['update']}")

        lines.append("-----------------------------")

        if has_vuln:
            vuln_new = sum(r["new"] for r in rows if r["key"] in ("vuln", "nuclei_result"))
            vuln_update = sum(r["update"] for r in rows if r["key"] in ("vuln", "nuclei_result"))
            if vuln_new > 0:
                lines.append(f"⚠️ 安全预警：检出 {vuln_new} 项漏洞风险，请尽快排查！\n")
            elif vuln_update > 0:
                lines.append(f"⚠️ 安全预警：监测到 {vuln_update} 项存量漏洞变动，请尽快排查！\n")

        lines.append("💡 提示：详情请登录 ARL-Next 控制台查看完整资产清单。")
        return "\n".join(lines)

    def _generate_markdown_payload(self):
        """兼容旧接口调用，输出纯文本"""
        return self._generate_plain_text_payload()

    def _generate_markdown_table_payload(self):
        """兼容旧接口调用，输出纯文本"""
        return self._generate_plain_text_payload()

    def _generate_markdown_card_payload(self):
        """兼容旧接口调用，输出纯文本"""
        return self._generate_plain_text_payload()

    def _generate_html_payload(self):
        """
        适用于邮件 HTML 渲染的自适应响应式卡片表格
        """
        if not self.has_any_data:
            return f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 620px; padding: 20px; border: 1px solid #e8e8e8; border-radius: 8px; background-color: #ffffff;">
    <h3 style="margin-top: 0; color: #1890ff; font-size: 18px;">🎯 [{self.task_name}] 任务完成通知</h3>
    <p style="color: #595959; font-size: 14px; margin-bottom: 0;">任务已执行完毕，本次未发现新增或变动资产。</p>
</div>"""

        rows, total_new, total_update, has_vuln = self._get_summary_data()

        vuln_banner = ""
        if has_vuln:
            vuln_new = sum(r["new"] for r in rows if r["key"] in ("vuln", "nuclei_result"))
            vuln_update = sum(r["update"] for r in rows if r["key"] in ("vuln", "nuclei_result"))
            if vuln_new > 0:
                vuln_banner = f"""<div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; font-size: 14px; color: #cf1322;">
    ⚠️ <b>安全风险预警</b>：检出 <strong>{vuln_new}</strong> 项漏洞风险，请尽快登录排查！
</div>"""
            elif vuln_update > 0:
                vuln_banner = f"""<div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; font-size: 14px; color: #cf1322;">
    ⚠️ <b>安全风险预警</b>：监测到 <strong>{vuln_update}</strong> 项存量漏洞变动，请尽快登录排查！
</div>"""

        table_rows = []
        for r in rows:
            table_rows.append(f"""<tr style="border-bottom: 1px solid #f0f0f0;">
    <td style="padding: 10px 12px; color: #262626;">{r['label']}</td>
    <td style="padding: 10px 12px; text-align: center; color: #52c41a; font-weight: 500;">{r['new']}</td>
    <td style="padding: 10px 12px; text-align: center; color: #1890ff; font-weight: 500;">{r['update']}</td>
</tr>""")

        rows_html = "\n".join(table_rows)

        return f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 620px; padding: 24px; border: 1px solid #e8e8e8; border-radius: 8px; background-color: #ffffff; color: #262626;">
    <h3 style="margin-top: 0; color: #1890ff; font-size: 18px; border-bottom: 1px solid #f0f0f0; padding-bottom: 12px; margin-bottom: 16px;">
        🎯 [{self.task_name}] 任务完成通知
    </h3>
    {vuln_banner}
    <div style="background-color: #fafafa; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 14px;">
        <span>🌟 <b>新增资产总计</b>: <strong style="color: #52c41a;">{total_new}</strong> 项</span>
        <span style="margin: 0 12px; color: #d9d9d9;">|</span>
        <span>🔄 <b>更新资产总计</b>: <strong style="color: #1890ff;">{total_update}</strong> 项</span>
    </div>
    <table style="width: 100%; border-collapse: collapse; font-size: 14px; text-align: left;">
        <thead>
            <tr style="background-color: #fafafa; border-bottom: 2px solid #e8e8e8;">
                <th style="padding: 10px 12px; color: #595959; font-weight: 600;">资产类型</th>
                <th style="padding: 10px 12px; text-align: center; color: #52c41a; font-weight: 600;">🌟 新增数量</th>
                <th style="padding: 10px 12px; text-align: center; color: #1890ff; font-weight: 600;">🔄 更新数量</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div style="font-size: 13px; color: #8c8c8c; border-top: 1px solid #f0f0f0; padding-top: 12px; margin-top: 16px;">
        💡 <b>提示</b>：本次任务已全部处理完毕，详情请登录 ARL-Next 控制台查看完整资产明细。
    </div>
</div>"""

    def _push_dingding(self):
        tpl = self._generate_plain_text_payload()
        ding_out = dingding_send(msg=tpl, access_token=Config.DINGDING_ACCESS_TOKEN,
                                 secret=Config.DINGDING_SECRET, msgtype="text",
                                 title=f"[{self.task_name[:30]}] 任务完成通知")
        if ding_out.get("errcode", 0) != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl[:50], ding_out))
            return False
        return True

    def _push_wx_work(self):
        tpl = self._generate_plain_text_payload()
        ding_out = wx_work_send(msg=tpl, webhook_url=Config.WX_WORK_WEBHOOK)
        if ding_out.get("errcode", 0) != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl[:50], ding_out))
            return False
        return True

    def _push_feishu(self):
        tpl = self._generate_plain_text_payload()
        feishu_out = feishu_send(msg=tpl, webhook_url=Config.FEISHU_WEBHOOK,
                                 secret=Config.FEISHU_SECRET,
                                 title=f"[{self.task_name[:30]}] 任务完成通知")
        if feishu_out.get("code", 0) != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl[:50], feishu_out))
            return False
        return True

    def _push_telegram(self):
        tpl = self._generate_plain_text_payload()
        try:
            tg_out = telegram_send(tpl, bot_token=Config.TG_BOT_TOKEN, chat_id=Config.TG_CHAT_ID)
            if not tg_out.get("ok"):
                logger.warning("Telegram发送失败 \n{}\n {}".format(tpl[:50], tg_out))
                return False
            return True
        except Exception as e:
            logger.warning("Telegram发送异常 \n{}\n {}".format(tpl[:50], str(e)))
            return False

    def _push_email(self):
        html = self._generate_html_payload()
        title = "[{}] 任务完成资产通知".format(self.task_name[:50])
        send_email(host=Config.EMAIL_HOST, port=Config.EMAIL_PORT, mail=Config.EMAIL_USERNAME,
                   password=Config.EMAIL_PASSWORD, to=Config.EMAIL_TO, title=title, html=html)
        return True

    def push_dingding(self):
        try:
            if Config.DINGDING_ACCESS_TOKEN and Config.DINGDING_SECRET:
                if self._push_dingding():
                    logger.info("push dingding succ")
                    return True

        except Exception as e:
            logger.warning(f"[{self.task_name}] push dingding error: {e}")

    def push_email(self):
        try:
            if Config.EMAIL_HOST and Config.EMAIL_USERNAME and Config.EMAIL_PASSWORD:
                self._push_email()
                logger.info("send email succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push email error: {e}")

    def push_feishu(self):
        try:
            if Config.FEISHU_WEBHOOK and Config.FEISHU_SECRET:
                self._push_feishu()
                logger.info("send feishu succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push feishu error: {e}")

    def push_wx_work(self):
        try:
            if Config.WX_WORK_WEBHOOK:
                self._push_wx_work()
                logger.info("send wx work succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push wx work error: {e}")

    def push_telegram(self):
        try:
            if getattr(Config, 'TG_BOT_TOKEN', None) and getattr(Config, 'TG_CHAT_ID', None):
                self._push_telegram()
                logger.info("send telegram succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push telegram error: {e}")


def message_push(asset_map, asset_counter, update_map=None, update_counter=None):
    if "task_complete" not in Config.PUSH_OPTIONS:
        return
    logger.info("ARL push run")
    p = Push(asset_map=asset_map, asset_counter=asset_counter, update_map=update_map, update_counter=update_counter)
    p.push_dingding()
    p.push_email()
    p.push_feishu()
    p.push_wx_work()
    p.push_telegram()

def _truncate_utf8_by_bytes(text: str, max_bytes: int, suffix: str = "") -> str:
    """按 UTF-8 字节上限截断纯文本，适配企业微信等按字节计数的推送通道"""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    suffix_bytes = suffix.encode("utf-8")
    budget = max(0, max_bytes - len(suffix_bytes))
    trimmed = raw[:budget].decode("utf-8", errors="ignore").rstrip()
    return f"{trimmed}{suffix}"


def unified_push(push_type: str, title: str, content: str, html_content: str = None):
    """
    统一消息推送入口，适配所有配置的有效渠道
    即时通讯渠道统一自动清洗 Markdown 语法，输出优美可读纯文本
    """
    if push_type not in Config.PUSH_OPTIONS:
        return

    plain_content = strip_markdown_syntax(content)
    clean_title = strip_markdown_syntax(title)

    # 钉钉
    if Config.DINGDING_ACCESS_TOKEN and Config.DINGDING_SECRET:
        try:
            res = dingding_send(plain_content, Config.DINGDING_ACCESS_TOKEN, Config.DINGDING_SECRET, msgtype="text", title=clean_title)
            if res.get("errcode", 0) != 0:
                logger.warning(f"unified_push dingding api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push dingding error: {e}")

    # 飞书
    if Config.FEISHU_WEBHOOK and Config.FEISHU_SECRET:
        try:
            res = feishu_send(plain_content, Config.FEISHU_WEBHOOK, Config.FEISHU_SECRET, title=clean_title)
            if res.get("code", 0) != 0:
                logger.warning(f"unified_push feishu api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push feishu error: {e}")

    # 企业微信（文本消息上限 2048 字节）
    if Config.WX_WORK_WEBHOOK:
        try:
            wx_content = _truncate_utf8_by_bytes(
                f"{clean_title}\n\n{plain_content}",
                2000,
                suffix="\n...（内容过长已截断，请登录控制台查看详情）",
            )
            res = wx_work_send(wx_content, Config.WX_WORK_WEBHOOK)
            if res.get("errcode", 0) != 0:
                logger.warning(f"unified_push wx_work api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push wx_work error: {e}")

    # 邮件 (优先使用定制 HTML 卡片；否则回退为转义纯文本换行格式)
    if Config.EMAIL_HOST and Config.EMAIL_USERNAME and Config.EMAIL_PASSWORD and Config.EMAIL_TO:
        try:
            if html_content:
                email_html = html_content
            else:
                escaped_body = html_lib.escape(plain_content).replace('\n', '<br>')
                email_html = f"<div><h3>{html_lib.escape(clean_title)}</h3><div>{escaped_body}</div></div>"
            send_email(Config.EMAIL_HOST, Config.EMAIL_PORT, Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD, Config.EMAIL_TO, clean_title, email_html)
        except Exception as e:
            logger.warning(f"unified_push email error: {e}")

    # Telegram (使用纯文本传输，单条上限 4096 字符)
    tg_token = getattr(Config, 'TG_BOT_TOKEN', None)
    tg_chat = getattr(Config, 'TG_CHAT_ID', None)
    if tg_token and tg_chat:
        try:
            tg_msg = f"{clean_title}\n\n{plain_content}"
            if len(tg_msg) > 4000:
                tg_msg = tg_msg[:3960].rstrip() + "\n...（内容过长已截断，请登录控制台查看详情）"
            res = telegram_send(tg_msg, tg_token, tg_chat)
            if not res.get("ok"):
                logger.warning(f"unified_push telegram api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push telegram error: {e}")


NUCLEI_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")
NUCLEI_SEVERITY_RANK = {sev: idx for idx, sev in enumerate(NUCLEI_SEVERITY_ORDER)}
NUCLEI_SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高危",
    "medium": "中危",
    "low": "低危",
    "info": "信息",
}
NUCLEI_SEVERITY_BADGE_STYLES = {
    "critical": ("#cf1322", "#fff1f0", "#ffa39e"),
    "high": ("#d4380d", "#fff2e8", "#ffbb96"),
    "medium": ("#d48806", "#fffbe6", "#ffe58f"),
    "low": ("#096dd9", "#e6f7ff", "#91d5ff"),
    "info": ("#595959", "#fafafa", "#d9d9d9"),
}
DEFAULT_NUCLEI_PUSH_SEVERITIES = ["critical", "high", "medium", "low"]


def normalize_nuclei_push_severities(severities, default=None):
    """规范化 Nuclei 推送严重等级列表，保留标准排序并去重。"""
    if severities is None:
        return list(default) if default is not None else list(DEFAULT_NUCLEI_PUSH_SEVERITIES)
    if isinstance(severities, str):
        raw_items = [part.strip().lower() for part in severities.split(",")]
    elif isinstance(severities, (list, tuple, set)):
        raw_items = [str(part).strip().lower() for part in severities if part is not None]
    else:
        return list(default) if default is not None else list(DEFAULT_NUCLEI_PUSH_SEVERITIES)

    allowed = {item for item in raw_items if item in NUCLEI_SEVERITY_RANK}
    return [sev for sev in NUCLEI_SEVERITY_ORDER if sev in allowed]


def filter_and_sort_nuclei_results(results, allowed_severities=None):
    """按严重等级白名单过滤 Nuclei 结果，并按 critical -> info 优先级排序。"""
    if not results:
        return []
    if allowed_severities is None:
        raw_cfg = getattr(Config, "NUCLEI_PUSH_SEVERITIES", None)
        if not isinstance(raw_cfg, (list, tuple, set, str)):
            raw_cfg = DEFAULT_NUCLEI_PUSH_SEVERITIES
        allowed = set(normalize_nuclei_push_severities(raw_cfg))
    else:
        allowed = set(normalize_nuclei_push_severities(allowed_severities))

    if not allowed:
        return []

    filtered = []
    for item in results:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("vuln_severity") or "").strip().lower()
        if sev in allowed:
            filtered.append(item)

    filtered.sort(
        key=lambda x: (
            NUCLEI_SEVERITY_RANK.get(str(x.get("vuln_severity") or "").strip().lower(), 99),
            str(x.get("template_id") or ""),
            str(x.get("vuln_url") or x.get("target") or x.get("host") or ""),
        )
    )
    return filtered


def count_nuclei_severities(results):
    """统计各严重等级命中数量。"""
    counts = {sev: 0 for sev in NUCLEI_SEVERITY_ORDER}
    for item in results or []:
        sev = str(item.get("vuln_severity") or "").strip().lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def _shorten_text(value: str, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)] + "..."


def build_nuclei_vuln_report(task_name, task_target, results, scope_name="", max_items=20):
    """构造 Nuclei 漏洞告警的标题、IM 纯文本与 HTML 邮件卡片。"""
    total = len(results)
    sev_counts = count_nuclei_severities(results)
    clean_task_name = str(task_name or "").strip() or "未命名任务"
    clean_target = _shorten_text(task_target or "-", 120)
    clean_scope = str(scope_name or "").strip()

    title = f"[Nuclei 漏洞告警-{clean_task_name[:30]}] 检出 {total} 项漏洞"

    summary_parts = [
        f"{NUCLEI_SEVERITY_LABELS[sev]} {sev_counts[sev]}"
        for sev in NUCLEI_SEVERITY_ORDER
        if sev_counts.get(sev, 0) > 0
    ]
    summary_line = " | ".join(summary_parts) if summary_parts else f"总计 {total}"

    lines = [
        "【ARL-Next Nuclei 漏洞告警】",
        f"任务名称：{clean_task_name}",
        f"扫描目标：{clean_target}",
    ]
    if clean_scope:
        lines.append(f"所属资产组：{clean_scope}")
    lines.append(f"命中统计：共 {total} 项（{summary_line}）")
    lines.append("-----------------------------")

    display_items = results[:max_items]
    for idx, item in enumerate(display_items, 1):
        sev = str(item.get("vuln_severity") or "").strip().lower()
        sev_label = NUCLEI_SEVERITY_LABELS.get(sev, sev or "未知")
        source_prefix = "[自建]" if str(item.get("template_source") or "").strip().lower() == "custom" else ""
        vuln_name = _shorten_text(item.get("vuln_name") or item.get("template_id") or "未命名漏洞", 120)
        template_id = str(item.get("template_id") or "-").strip()
        vuln_url = _shorten_text(item.get("vuln_url") or item.get("target") or item.get("host") or "-", 180)
        lines.append(f"{idx}. [{sev_label}]{source_prefix} {vuln_name} ({template_id})")
        lines.append(f"   命中地址：{vuln_url}")

    lines.append("-----------------------------")
    if total > max_items:
        lines.append(f"… 共检出 {total} 项漏洞，其余 {total - max_items} 项请登录 ARL-Next 控制台查看。")
    lines.append("💡 提示：请尽快核验漏洞详情并开展修复。")
    plain_content = "\n".join(lines)

    # 构造邮件 HTML 表格
    badge_html_parts = []
    for sev in NUCLEI_SEVERITY_ORDER:
        cnt = sev_counts.get(sev, 0)
        if cnt <= 0:
            continue
        fg, bg, border = NUCLEI_SEVERITY_BADGE_STYLES[sev]
        badge_html_parts.append(
            f'<span style="display: inline-block; padding: 2px 8px; margin-right: 6px; border-radius: 4px; '
            f'font-size: 12px; font-weight: 600; color: {fg}; background-color: {bg}; border: 1px solid {border};">'
            f'{NUCLEI_SEVERITY_LABELS[sev]}: {cnt}</span>'
        )
    badges_html = "".join(badge_html_parts)

    scope_row_html = ""
    if clean_scope:
        scope_row_html = f'<div style="margin-top: 4px;"><b>所属资产组</b>：{html_lib.escape(clean_scope)}</div>'

    table_rows = []
    for idx, item in enumerate(display_items, 1):
        sev = str(item.get("vuln_severity") or "").strip().lower()
        sev_label = NUCLEI_SEVERITY_LABELS.get(sev, sev or "未知")
        fg, bg, border = NUCLEI_SEVERITY_BADGE_STYLES.get(sev, ("#595959", "#fafafa", "#d9d9d9"))
        is_custom = str(item.get("template_source") or "").strip().lower() == "custom"
        source_badge = (
            '<span style="display: inline-block; padding: 1px 5px; margin-left: 4px; border-radius: 4px; '
            'font-size: 11px; color: #531dab; background-color: #f9f0ff; border: 1px solid #d3adf7;">自建</span>'
            if is_custom else ""
        )
        template_id = html_lib.escape(str(item.get("template_id") or "-"))
        vuln_name = html_lib.escape(str(item.get("vuln_name") or item.get("template_id") or "未命名漏洞"))
        vuln_url = html_lib.escape(str(item.get("vuln_url") or item.get("target") or item.get("host") or "-"))
        table_rows.append(
            f'<tr style="border-bottom: 1px solid #f0f0f0;">'
            f'<td style="padding: 8px 10px; color: #595959;">{idx}</td>'
            f'<td style="padding: 8px 10px;"><span style="display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 12px; color: {fg}; background-color: {bg}; border: 1px solid {border};">{html_lib.escape(sev_label)}</span></td>'
            f'<td style="padding: 8px 10px; font-family: monospace; font-size: 12px; color: #262626;">{template_id}{source_badge}</td>'
            f'<td style="padding: 8px 10px; color: #262626;">{vuln_name}</td>'
            f'<td style="padding: 8px 10px; color: #1890ff; word-break: break-all;">{vuln_url}</td>'
            f'</tr>'
        )

    trunc_html = ""
    if total > max_items:
        trunc_html = (
            f'<div style="margin-top: 10px; font-size: 13px; color: #8c8c8c;">'
            f'… 共检出 {total} 项漏洞，以上展示前 {max_items} 项，完整明细请登录 ARL-Next 控制台查看。</div>'
        )

    html_content = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 780px; padding: 24px; border: 1px solid #e8e8e8; border-radius: 8px; background-color: #ffffff; color: #262626;">
    <h3 style="margin-top: 0; color: #cf1322; font-size: 18px; border-bottom: 1px solid #f0f0f0; padding-bottom: 12px; margin-bottom: 16px;">
        🚨 {html_lib.escape(clean_task_name)} - Nuclei 漏洞告警
    </h3>
    <div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 14px;">
        <div><b>扫描目标</b>：{html_lib.escape(clean_target)}</div>
        {scope_row_html}
        <div style="margin-top: 8px;"><b>检出统计（共 {total} 项）</b>：{badges_html}</div>
    </div>
    <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
        <thead>
            <tr style="background-color: #fafafa; border-bottom: 2px solid #e8e8e8;">
                <th style="padding: 8px 10px; color: #595959; width: 42px;">#</th>
                <th style="padding: 8px 10px; color: #595959; width: 70px;">等级</th>
                <th style="padding: 8px 10px; color: #595959;">模板 ID</th>
                <th style="padding: 8px 10px; color: #595959;">漏洞名称</th>
                <th style="padding: 8px 10px; color: #595959;">命中地址</th>
            </tr>
        </thead>
        <tbody>
            {"".join(table_rows)}
        </tbody>
    </table>
    {trunc_html}
    <div style="font-size: 12px; color: #8c8c8c; border-top: 1px solid #f0f0f0; padding-top: 12px; margin-top: 16px;">
        💡 <b>提示</b>：请尽快登录 ARL-Next 控制台核验漏洞详情并开展修复。
    </div>
</div>"""

    return title, plain_content, html_content, sev_counts


def nuclei_vuln_push(task_id: str, results: list, scope_id: str = "", task_info: dict = None) -> bool:
    """过滤、聚合 Nuclei 漏洞结果并分发至已配置的 IM/邮件通道与全局 Webhook。"""
    push_options = getattr(Config, "PUSH_OPTIONS", None)
    if not isinstance(push_options, (list, tuple, set)) or "nuclei_vuln" not in push_options:
        return False

    filtered = filter_and_sort_nuclei_results(results)
    if not filtered:
        return False

    from bson import ObjectId
    from app.utils.conn import conn_db

    if task_info is None and task_id and ObjectId.is_valid(str(task_id)):
        try:
            task_info = conn_db("task").find_one({"_id": ObjectId(str(task_id))})
        except Exception as e:
            logger.warning(f"nuclei_vuln_push fetch task failed ({task_id}): {e}")
            task_info = None

    scope_name = ""
    if scope_id and ObjectId.is_valid(str(scope_id)):
        try:
            scope_doc = conn_db("asset_scope").find_one({"_id": ObjectId(str(scope_id))}, {"name": 1})
            if scope_doc:
                scope_name = scope_doc.get("name", "")
        except Exception as e:
            logger.warning(f"nuclei_vuln_push fetch scope failed ({scope_id}): {e}")

    task_name = (task_info or {}).get("name", "")
    task_target = (task_info or {}).get("target", "")
    title, plain_content, html_content, _ = build_nuclei_vuln_report(
        task_name=task_name,
        task_target=task_target,
        results=filtered,
        scope_name=scope_name,
    )

    unified_push("nuclei_vuln", title, plain_content, html_content=html_content)

    try:
        from app.services import webhook
        webhook.nuclei_vuln_web_hook(
            task_id=str(task_id or ""),
            scope_id=str(scope_id or ""),
            nuclei_results=filtered,
            task_data=task_info,
        )
    except Exception as e:
        logger.warning(f"nuclei_vuln_push webhook dispatch failed: {e}")

    return True


def dict2dingding_mark(info_list):
    if not info_list:
        return ""

    title_tpl = '  \t\t  '.join(map(str, info_list[0].keys()))
    items_tpl = ""
    cnt = 0
    for row in info_list:
        cnt += 1
        row = ' \t '.join(map(str, row.values()))
        items_tpl += "{}. {}\n".format(cnt, row)

    return "{}\n{}".format(title_tpl, items_tpl)


def dingding_send(msg, access_token, secret, msgtype="text", title="灯塔消息推送"):
    ding_url = "https://oapi.dingtalk.com/robot/send?access_token={}".format(access_token)
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    param = "&timestamp={}&sign={}".format(timestamp, sign)
    ding_url = ding_url + param
    send_json = {
        "msgtype": msgtype,
        "text": {
            "content": msg
        },
        "markdown": {
            "title": title,
            "text": msg
        }
    }
    # 钉钉请求携带 access_token 与加签 secret，必须校验服务端证书。
    conn = http_req(ding_url, method='post', json=send_json, verify=True, proxy_domain="intel")
    return conn.json()


def send_email(host, port, mail, password, to, title, html, smtp_timeout=10):
    context = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=smtp_timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=smtp_timeout)

    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = mail
    msg['To'] = to
    part1 = MIMEText(html, "html", "utf-8")
    msg.attach(part1)
    server.login(mail, password)
    server.send_message(msg)
    server.close()


def dict2table(info_list):
    if not info_list:
        return ""
    html = ""
    table_style = 'style="border-collapse: collapse;"'
    table_start = '<table {}>\n'.format(table_style)
    table_end = '</table>\n'
    style = 'style="border: 0.5pt solid windowtext;"'
    thead_start = '<thead><tr><th {}>序号</th><th {}>\n'.format(style, style)
    thead_end = '\n</th></tr></thead>'
    th_join_tpl = '</th>\n<th {}>'.format(style)
    thead_tpl = th_join_tpl.join(map(str, info_list[0].keys()))
    html += table_start
    html += thead_start
    html += thead_tpl
    html += thead_end

    tbody = "<tbody>\n"
    cnt = 0
    for row in info_list:
        cnt += 1
        td_join_tpl = '</td>\n<td {}>'.format(style)
        row_start = '<tr><td {}>{}</td>\n<td {}>'.format(style, cnt, style)
        items = [str(x).replace('>', "&#x3e;").replace('<', "&#x3c;") for x in row.values()]
        row = td_join_tpl.join(items)
        row_end = '</td>\n</tr>'
        row_tpl = row_start + row + row_end
        tbody = tbody + row_tpl + "\n"

    html = html + tbody + "</tbody>" + table_end

    return html


def feishu_send(msg, webhook_url, secret, title="灯塔消息推送"):
    timestamp = str(int(time.time()))
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode('utf-8')

    send_data = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [
                        [{
                            "tag": "text",
                            "text": msg
                        }]
                    ]
                }
            }
        }
    }
    # 飞书请求携带 webhook 签名密钥，必须校验服务端证书。
    conn = http_req(webhook_url, method='post', json=send_data, verify=True, proxy_domain="intel")
    return conn.json()


def wx_work_send(msg, webhook_url):
    send_data = {
        "msgtype": "text",
        "text": {
            "content": msg
        }
    }
    # 企业微信 webhook 携带敏感凭据，必须校验服务端证书。
    conn = http_req(webhook_url, method='post', json=send_data, verify=True, proxy_domain="intel")
    return conn.json()


def telegram_send(msg, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg
    }
    try:
        # Telegram 请求携带 Bot Token，必须校验服务端证书。
        conn = http_req(url, method='post', json=payload, timeout=10, verify=True, proxy_domain="intel")
        return conn.json()
    except Exception as e:
        logger.warning(f"telegram_send error: {e}")
        return {}
