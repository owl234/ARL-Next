# ARL-Next/app/utils/time.py
"""
时间工具类 —— 基于 Arrow
- 统一 UTC 时间入口（避免 datetime.utcnow() 弃用）
- 提供本地时间格式化、解析
- 时区安全，与 MongoDB 兼容（返回 naive UTC）
"""

from datetime import datetime

import arrow


# ═══════════════════════════════════════════════════════════
# 一、核心：UTC 时间
# ═══════════════════════════════════════════════════════════

def utcnow():
    """
    当前 UTC 时间（naive datetime）
    - 用于数据库存储
    - 与 PyMongo 读写行为一致
    - Arrow 默认时区感知，需转为 naive 兼容 MongoDB
    """
    return arrow.utcnow().naive


def utcnow_arrow():
    """当前 UTC 时间（Arrow 对象）"""
    return arrow.utcnow()


def utcnow_aware():
    """当前 UTC 时间（timezone-aware datetime）"""
    return arrow.utcnow().datetime


def utcnow_str(fmt="YYYY-MM-DD HH:mm:ss"):
    """当前 UTC 时间字符串"""
    return arrow.utcnow().format(fmt)


def utc_now_iso():
    """当前 UTC 时间的 ISO 8601 字符串"""
    return arrow.utcnow().isoformat()


# ═══════════════════════════════════════════════════════════
# 二、本地时间（保留原有 API 兼容）
# ═══════════════════════════════════════════════════════════

def now():
    """当前本地时间（Arrow 对象）"""
    return arrow.now()


def now_naive():
    """当前本地时间（naive datetime）"""
    return arrow.now().naive


def curr_date():
    """当前本地时间字符串（兼容原有）"""
    return arrow.now().format("YYYY-MM-DD HH:mm:ss")


def curr_date_obj():
    """当前本地时间对象（无微秒，兼容原有）"""
    return arrow.now().replace(microsecond=0).naive


# ═══════════════════════════════════════════════════════════
# 三、时间戳转换（兼容原有）
# ═══════════════════════════════════════════════════════════

def time2date(secs):
    """
    时间戳 → 本地时间字符串
    :param secs: Unix 时间戳（秒）
    """
    return arrow.get(secs).to("local").format("YYYY-MM-DD HH:mm:ss")


def date2time(date_str):
    """
    本地时间字符串 → Unix 时间戳
    :param date_str: "2026-09-29 11:30:00"
    """
    return arrow.get(date_str, "YYYY-MM-DD HH:mm:ss").timestamp()


def ts_to_arrow(secs):
    """时间戳 → Arrow 对象"""
    return arrow.get(secs)


def arrow_to_ts(dt):
    """Arrow 对象 → 时间戳"""
    return dt.timestamp()


# ═══════════════════════════════════════════════════════════
# 四、解析（兼容原有 parse_datetime，功能更强）
# ═══════════════════════════════════════════════════════════

def parse_datetime(s):
    """
    解析 ISO 8601 格式（兼容原有，支持更多格式）
    :param s: "2026-09-29T03:30:00Z" 或 "2026-09-29 11:30:00+08:00"
    :return: naive datetime（本地时间）
    """
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return arrow.get(s).naive
    except Exception:
        return None


def parse_utc(s):
    """
    解析时间字符串为 naive UTC datetime
    :param s: 各种格式的时间字符串
    :return: naive UTC datetime
    """
    if not s:
        return None
    try:
        return arrow.get(s).to("UTC").naive
    except Exception:
        return None


def parse_arrow(s):
    """解析时间字符串为 Arrow 对象"""
    if not s:
        return None
    return arrow.get(s)


# ═══════════════════════════════════════════════════════════
# 五、格式化
# ═══════════════════════════════════════════════════════════

def format_datetime(dt, fmt="YYYY-MM-DD HH:mm:ss"):
    """
    格式化任意时间对象
    :param dt: datetime / Arrow / 时间戳 / 字符串
    """
    if dt is None:
        return None
    return arrow.get(dt).format(fmt)


def to_iso(dt):
    """datetime → ISO 8601 字符串"""
    if dt is None:
        return None
    return arrow.get(dt).isoformat()


def to_iso_utc(dt):
    """datetime → UTC ISO 8601 字符串"""
    if dt is None:
        return None
    return arrow.get(dt).to("UTC").isoformat()


# ═══════════════════════════════════════════════════════════
# 六、时区转换
# ═══════════════════════════════════════════════════════════

def to_naive_utc(dt):
    """把任意时间对象转为 naive UTC datetime"""
    if dt is None:
        return None
    return arrow.get(dt).to("UTC").naive


def to_local(dt):
    """把任意时间对象转为本地时间（Arrow 对象）"""
    if dt is None:
        return None
    return arrow.get(dt).to("local")


def to_timezone(dt, tz):
    """时区转换"""
    if dt is None:
        return None
    return arrow.get(dt).to(tz)


# ═══════════════════════════════════════════════════════════
# 七、相对时间（"3 minutes ago"）
# ═══════════════════════════════════════════════════════════

def humanize(dt, locale="zh-cn"):
    """
    人类可读的时间描述
    :param dt: 目标时间
    :param locale: 语言（zh-cn / en / ja ...）
    :return: "3 分钟前" / "2 小时前"
    """
    if dt is None:
        return None
    return arrow.get(dt).humanize(locale=locale)


def humanize_diff(start, end=None):
    """
    计算时间差的人类可读描述
    :param start: 起始时间
    :param end: 结束时间（默认当前）
    """
    start_arrow = arrow.get(start)
    if end:
        return start_arrow.humanize(arrow.get(end))
    return start_arrow.humanize()


# ═══════════════════════════════════════════════════════════
# 八、时间计算
# ═══════════════════════════════════════════════════════════

def shift(dt, **kwargs):
    """
    时间偏移
    :param dt: 基准时间
    :param kwargs: years / months / weeks / days / hours / minutes / seconds
    :example:
        shift(now(), days=-7)      # 7 天前
        shift(now(), hours=2)      # 2 小时后
    """
    if dt is None:
        return None
    return arrow.get(dt).shift(**kwargs)


def diff_seconds(start, end=None):
    """计算时间差（秒）"""
    if end is None:
        end = utcnow()
    return (arrow.get(end) - arrow.get(start)).total_seconds()


def diff_days(start, end=None):
    """计算时间差（天）"""
    return diff_seconds(start, end) / 86400


def start_of_day(dt=None):
    """当天开始时间（00:00:00）"""
    if dt is None:
        dt = utcnow()
    return arrow.get(dt).floor("day").naive


def end_of_day(dt=None):
    """当天结束时间（23:59:59.999999）"""
    if dt is None:
        dt = utcnow()
    return arrow.get(dt).ceil("day").naive


def start_of_month(dt=None):
    """当月开始时间"""
    if dt is None:
        dt = utcnow()
    return arrow.get(dt).floor("month").naive


def start_of_week(dt=None):
    """本周开始时间（周一）"""
    if dt is None:
        dt = utcnow()
    return arrow.get(dt).floor("week").naive


# ═══════════════════════════════════════════════════════════
# 九、区间工具（用于数据库范围查询）
# ═══════════════════════════════════════════════════════════

def last_n_days(n):
    """
    最近 n 天的 [start, end] 区间
    :return: (start_naive_utc, end_naive_utc)
    """
    end = utcnow()
    start = arrow.get(end).shift(days=-n).naive
    return start, end


def last_n_hours(n):
    """最近 n 小时的 [start, end] 区间"""
    end = utcnow()
    start = arrow.get(end).shift(hours=-n).naive
    return start, end


def date_range(start, end):
    """
    生成日期区间（用于遍历）
    :param start: 起始日期字符串 "2026-09-01"
    :param end: 结束日期字符串 "2026-09-30"
    :yield: Arrow 对象
    """
    start_arrow = arrow.get(start)
    end_arrow = arrow.get(end)
    current = start_arrow
    while current <= end_arrow:
        yield current
        current = current.shift(days=1)