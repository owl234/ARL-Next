import re
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
            lines.append(f"⚠️ 安全预警：检出 {vuln_new} 项漏洞风险，请尽快排查！\n")

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
            vuln_banner = f"""<div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; font-size: 14px; color: #cf1322;">
    ⚠️ <b>安全风险预警</b>：检出 <strong>{vuln_new}</strong> 项漏洞风险，请尽快登录排查！
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

def unified_push(push_type: str, title: str, content: str):
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

    # 企业微信
    if Config.WX_WORK_WEBHOOK:
        try:
            wx_content = f"{clean_title}\n\n{plain_content}"
            res = wx_work_send(wx_content, Config.WX_WORK_WEBHOOK)
            if res.get("errcode", 0) != 0:
                logger.warning(f"unified_push wx_work api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push wx_work error: {e}")

    # 邮件 (Email 渲染原生 HTML，若无特定 html 则以纯文本换行格式组织)
    if Config.EMAIL_HOST and Config.EMAIL_USERNAME and Config.EMAIL_PASSWORD and Config.EMAIL_TO:
        try:
            html = plain_content.replace('\n', '<br>')
            html = f"<div><h3>{clean_title}</h3><div>{html}</div></div>"
            send_email(Config.EMAIL_HOST, Config.EMAIL_PORT, Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD, Config.EMAIL_TO, clean_title, html)
        except Exception as e:
            logger.warning(f"unified_push email error: {e}")

    # Telegram (使用纯文本传输)
    tg_token = getattr(Config, 'TG_BOT_TOKEN', None)
    tg_chat = getattr(Config, 'TG_CHAT_ID', None)
    if tg_token and tg_chat:
        try:
            tg_msg = f"{clean_title}\n\n{plain_content}"
            res = telegram_send(tg_msg, tg_token, tg_chat)
            if not res.get("ok"):
                logger.warning(f"unified_push telegram api error: {res}")
        except Exception as e:
            logger.warning(f"unified_push telegram error: {e}")


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
