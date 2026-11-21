import time
import datetime


def time2date(secs):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(secs))


def date2time(date):
    struct = time.strptime(date, '%Y-%m-%d %H:%M:%S')
    return time.mktime(struct)


def curr_date():
    return time2date(time.time())


def curr_date_obj():
    return datetime.datetime.now().replace(microsecond=0)


def to_datetime_obj(value, fallback_oid=None):
    """
    将 datetime / 字符串 / ObjectId 统一收敛为本地时区 naive datetime（精确到秒），
    与 curr_date_obj() 的存储规范保持一致。
    """
    if isinstance(value, datetime.datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.replace(microsecond=0)

    if isinstance(value, str):
        raw = value.strip()
        if raw:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(raw, fmt).replace(microsecond=0)
                except ValueError:
                    continue
            try:
                iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
                dt = datetime.datetime.fromisoformat(iso_raw)
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt.replace(microsecond=0)
            except ValueError:
                pass

    if fallback_oid is not None:
        try:
            from bson import ObjectId
            oid = fallback_oid if isinstance(fallback_oid, ObjectId) else ObjectId(str(fallback_oid))
            return oid.generation_time.astimezone().replace(tzinfo=None).replace(microsecond=0)
        except Exception:
            pass

    return None


def format_datetime_str(value):
    """将 datetime 或时间字符串格式化为标准 YYYY-MM-DD HH:MM:SS 字符串。"""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    return str(value)


# 参考： https://github.com/PyGithub/PyGithub/blob/0245b758ca323dfa18cd7910d50300ca42514999/github/GithubObject.py#L173
def parse_datetime(s):
    if len(s) == 24:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.000Z")

    elif len(s) >= 25:
        return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S") + (
            1 if s[19] == "-" else -1
        ) * datetime.timedelta(hours=int(s[20:22]), minutes=int(s[23:25]))

    else:
        date1 = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return date1 + datetime.timedelta(hours=8)
