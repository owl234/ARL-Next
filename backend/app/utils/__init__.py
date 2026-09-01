import subprocess
import shlex
import random
import string
import string
import os
import re
import sys
import hashlib
import threading
import contextvars
import concurrent.futures
try:
    from celery.utils.log import get_task_logger
except ImportError:
    import logging
    get_task_logger = logging.getLogger

arl_task_id_var = contextvars.ContextVar('arl_task_id', default='global')

class ContextAwareThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
    def submit(self, fn, *args, **kwargs):
        context = contextvars.copy_context()
        return super().submit(context.run, fn, *args, **kwargs)

try:
    import colorlog
except ImportError:
    colorlog = None
import logging
import dns.resolver
from tld import get_tld
from datetime import datetime
try:
    from celery import current_task
except ImportError:
    current_task = None

from .conn import http_req, conn_db
from .http import get_title, get_headers
from .domain import (
    check_domain_black, is_valid_domain, is_in_scope, is_in_scopes, 
    is_valid_fuzz_domain, is_forbidden_domain,
    extract_dynamic_ip_from_domain, is_private_or_reserved_ip, is_dynamic_ip_edge_domain
)
from .ip import is_vaild_ip_target, not_in_black_ips, get_ip_asn, get_ip_city, get_ip_type
from .arl import arl_domain, get_asset_domain_by_id
from .time import curr_date, time2date, curr_date_obj
from .url import rm_similar_url, get_hostname, normal_url, same_netloc, verify_cert, url_ext
from .cert import get_cert, extract_domains_from_cert
from .arlupdate import arl_update
from .cdn import get_cdn_name_by_cname, get_cdn_name_by_ip, get_cdn_name_by_headers, get_cdn_name_by_ssl, get_cdn_name_comprehensive
try:
    from .device import device_info
except ImportError:
    device_info = None

try:
    from .cron import check_cron, check_cron_interval
except ImportError:
    check_cron, check_cron_interval = None, None
from .query_loader import load_query_plugins
import re

def get_safe_dict_path(filename):
    from app.config import Config
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("字典文件名不能为空")
    
    clean_filename = filename.strip()
    # 杜绝任何形式的路径穿越字符
    if '..' in clean_filename or '/' in clean_filename or '\\' in clean_filename:
        raise ValueError(f"不合法的字典文件名（禁止包含路径分隔符或穿越符号）: {filename}")
    
    if not clean_filename.endswith('.txt'):
        clean_filename += '.txt'
    
    basedir = getattr(Config, 'basedir', None) or os.path.dirname(os.path.dirname(__file__))
    base_dir = os.path.abspath(os.path.join(basedir, 'dicts'))
    target_path = os.path.abspath(os.path.join(base_dir, clean_filename))
    
    # 严格确保目标路径位于 dicts 目录下
    if os.path.commonpath([base_dir, target_path]) != base_dir:
        raise ValueError(f"越界访问字典目录: {filename}")
        
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"字典文件不存在: {target_path}")
        
    return target_path

def load_file_generator(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield line

def load_file(path):
    if os.path.exists(path) and os.path.getsize(path) > 50 * 1024 * 1024:
        raise Exception(f"字典超过 50MB ({path})，为防止系统 OOM，禁止通过全量模式加载。")
    with open(path, "r+", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def exec_system(cmd, **kwargs):
    cmd = " ".join(cmd)
    timeout = 4 * 60 * 60

    if kwargs.get('timeout'):
        timeout = kwargs['timeout']
        kwargs.pop('timeout')

    completed = subprocess.run(shlex.split(cmd), timeout=timeout, check=False, close_fds=True, **kwargs)

    return completed


def check_output(cmd, **kwargs):
    cmd = " ".join(cmd)
    timeout = 4 * 60 * 60

    if kwargs.get('timeout'):
        timeout = kwargs.pop('timeout')

    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    output = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, timeout=timeout, check=False,
               **kwargs).stdout
    return output


def random_choices(k=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))


import queue
import atexit


def gen_md5(s):
    return hashlib.md5(s.encode()).hexdigest()


_SYSLOG_LOCK = threading.Lock()

class MongoSyslogHandler(logging.Handler):
    """
    进程感知异步有界缓冲池 Mongo Syslog Handler
    消除同步 insert_one 对主业务/扫描任务的 I/O 阻塞与 WiredTiger 脏页风暴，
    同时自动感知 POSIX fork，确保每个 Celery Worker 子进程都拥有活跃独立的日志消费守护线程。
    """
    _pid = None
    _queue = None
    _stop_event = None
    _worker_thread = None

    def __init__(self):
        super().__init__()
        self._ensure_worker()

    @classmethod
    def _ensure_worker(cls):
        current_pid = os.getpid()
        # 1. 跨进程检测或线程健康状态检查
        if (
            cls._pid != current_pid
            or cls._worker_thread is None
            or not cls._worker_thread.is_alive()
            or cls._queue is None
        ):
            with _SYSLOG_LOCK:
                # 跨进程 fork 产生的新进程，重置专属队列与守护线程
                if cls._pid != current_pid:
                    cls._pid = current_pid
                    cls._queue = queue.Queue(maxsize=2000)
                    cls._stop_event = threading.Event()
                    cls._worker_thread = threading.Thread(
                        target=cls._batch_flush_worker,
                        args=(cls._pid, cls._queue, cls._stop_event),
                        daemon=True,
                        name=f"MongoSyslogFlushThread-{current_pid}"
                    )
                    cls._worker_thread.start()
                    try:
                        atexit.register(cls._flush_on_exit)
                    except Exception:
                        pass
                # 同进程内守护线程异常退出自愈
                elif (
                    cls._worker_thread is None
                    or not cls._worker_thread.is_alive()
                    or cls._queue is None
                ):
                    cls._queue = queue.Queue(maxsize=2000) if cls._queue is None else cls._queue
                    cls._stop_event = threading.Event()
                    cls._worker_thread = threading.Thread(
                        target=cls._batch_flush_worker,
                        args=(cls._pid, cls._queue, cls._stop_event),
                        daemon=True,
                        name=f"MongoSyslogFlushThread-{current_pid}"
                    )
                    cls._worker_thread.start()

    @classmethod
    def _batch_flush_worker(cls, target_pid, target_queue, stop_event):
        while not stop_event.is_set():
            batch = []
            try:
                item = target_queue.get(timeout=1.0)
                batch.append(item)
                while len(batch) < 50:
                    try:
                        batch.append(target_queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                continue

            if batch:
                try:
                    conn_db('syslog').insert_many(batch, ordered=False)
                except Exception:
                    # 瞬时抖动时短暂休眠 0.3s 重试一次，提升网络异常时的容错率
                    try:
                        time.sleep(0.3)
                        conn_db('syslog').insert_many(batch, ordered=False)
                    except Exception:
                        pass
                finally:
                    for _ in range(len(batch)):
                        target_queue.task_done()

    @classmethod
    def _flush_on_exit(cls):
        if cls._stop_event:
            cls._stop_event.set()
        if cls._queue is not None:
            batch = []
            while not cls._queue.empty():
                try:
                    batch.append(cls._queue.get_nowait())
                except queue.Empty:
                    break
            if batch:
                try:
                    conn_db('syslog').insert_many(batch, ordered=False)
                except Exception:
                    pass

    def emit(self, record):
        try:
            self._ensure_worker()
            task_id = str(arl_task_id_var.get() or "global")

            level = record.levelname.lower()
            if level == 'warn':
                level = 'warning'
            elif level in ['fatal', 'critical']:
                level = 'error'

            log_doc = {
                "task_id": task_id,
                "level": level,
                "title": getattr(record, 'funcName', '系统运行'),
                "message": str(record.getMessage()),
                "create_time": datetime.now().replace(microsecond=0)
            }
            # 非阻塞入队，队列满时丢弃以保护业务主线程零 I/O 阻塞
            if self._queue is not None:
                try:
                    self._queue.put_nowait(log_doc)
                except queue.Full:
                    pass
        except Exception:
            pass # 捕获异常防止拖垮主业务进程

def init_logger():
    if colorlog:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            fmt = '%(log_color)s[%(asctime)s] [%(levelname)s] '
                  '[%(threadName)s] [%(filename)s:%(lineno)d] %(message)s', datefmt = "%Y-%m-%d %H:%M:%S"))
        logger = colorlog.getLogger('arlv2')
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            fmt = '[%(asctime)s] [%(levelname)s] [%(threadName)s] [%(filename)s:%(lineno)d] %(message)s', datefmt = "%Y-%m-%d %H:%M:%S"))
        logger = logging.getLogger('arlv2')

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    # 💥 添加我们自定义的 MongoDB 拦截器
    mongo_handler = MongoSyslogHandler()
    mongo_handler.setLevel(logging.INFO)
    logger.addHandler(mongo_handler)
    
    logger.propagate = False


def get_logger():
    """
    根据类型创建日志记录器。
    :return: 日志记录器
    """
    if 'celery' in sys.argv[0]: # 内存字符串的物理匹配
        task_logger = get_task_logger(__name__)
        # 确保 task_logger 也挂载了我们的 MongoDB 拦截器
        has_mongo_handler = any(isinstance(h, MongoSyslogHandler) for h in task_logger.handlers)
        if not has_mongo_handler:
            mongo_handler = MongoSyslogHandler()
            mongo_handler.setLevel(logging.INFO)
            task_logger.addHandler(mongo_handler)
        return task_logger

    logger = logging.getLogger('arlv2')
    if not logger.handlers:
        init_logger()

    return logger


def get_ip(domain, log_flag=True):
    domain = domain.strip()
    logger = get_logger()
    ips = []
    try:
        answers = dns.resolver.resolve(domain, 'A')
        for rdata in answers:
            if rdata.address == '0.0.0.1':
                continue
            ips.append(rdata.address)
    except dns.resolver.NXDOMAIN as e:
        if log_flag:
            logger.info("{} {}".format(domain, e))

    except Exception as e:
        if log_flag:
            logger.warning("{} {}".format(domain, e))

    return ips


def get_cname(domain, log_flag=True):
    logger = get_logger()
    cnames = []
    try:
        answers = dns.resolver.resolve(domain, 'CNAME')
        for rdata in answers:
            cnames.append(str(rdata.target).strip(".").lower())
    except dns.resolver.NoAnswer as e:
        if log_flag:
            logger.debug(e)
    except Exception as e:
        logger.warning("{} {}".format(domain, e))

    return cnames


def domain_parsed(domain, fail_silently=True):
    """
    将域名拆分为主域名、域名、子域名
    :param domain:
    :param fail_silently:
    :return:
    """
    domain = domain.strip()
    try:
        res = get_tld(domain, fix_protocol=True,  as_object=True)
        item = {
            "subdomain": res.subdomain,
            "domain":res.domain,
            "fld": res.fld
        }
        return item
    except Exception as e:
        if not fail_silently:
            raise e


def get_fld(d):
    """获取域名的主域"""
    res = domain_parsed(d)
    if res:
        return res["fld"]


def gen_filename(site):
    filename = site.replace('://', '_')

    return re.sub(r'[^\w\-_\\. ]', '_', filename)


def build_ret(error, data):
    if isinstance(error, str):
        error = {
            "message": error,
            "code": 999,
        }

    ret = {}
    ret.update(error)
    ret["data"] = data
    msg = error["message"]

    if error["code"] != 200:
        for k in data:
            if k.endswith("id"):
                continue
            if not data[k]:
                continue
            if isinstance(data[k], str):
                msg += " {}:{}".format(k, data[k])

    ret["message"] = msg
    return ret


def kill_child_process(pid):
    logger = get_logger()
    try:
        import psutil
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            logger.info("kill child_process {}".format(child))
            child.kill()
    except ImportError:
        logger.warning("psutil module is missing, cannot kill child processes.")


def exit_gracefully(signum, frame):
    logger = get_logger()
    logger.info('Receive signal {} frame {}'.format(signum, frame))
    # 强制退出前先刷新未写入的日志队列
    try:
        MongoSyslogHandler._flush_on_exit()
    except Exception:
        pass
    pid = os.getpid()
    kill_child_process(pid)
    try:
        import psutil
        parent = psutil.Process(pid)
        logger.info("kill self {}".format(parent))
        parent.kill()
    except ImportError:
        logger.warning("psutil missing, fallback to sys.exit")
        sys.exit(0)


def truncate_string(s):
    if len(s) > 30:
        truncated_string = s[:30]
        return truncated_string + "..."
    else:
        return s


def is_valid_exclude_ports(exclude_ports):
    """
    检查 nmap 中的排除端口范围是否合法
    """
    port_pattern = r'(\d+(-\d+)?,?)+'

    match = re.fullmatch(port_pattern, exclude_ports)

    if match:
        parts = exclude_ports.split(',')
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start > end or not (0 <= start <= 65535) or not (0 <= end <= 65535):
                    return False
            else:
                if not (0 <= int(part) <= 65535):
                    return False
        return True
    else:
        return False


from .user import user_login, user_login_header, auth, user_logout, change_pass, user_refresh_token
from .push import message_push
from .fingerprint import parse_human_rule, transform_rule_map


def clean_task_data(task_id):
    """
    清理指定任务运行过程中产生的各表数据，用于任务无副作用的重新执行
    """
    logger = get_logger()
    logger.info(f"Cleaning existing data for task {task_id}")
    table_list = [
        "cert", "domain", "fileleak", "ip", "service",
        "site", "url", "vuln", "cip", "npoc_service", 
        "wih", "nuclei_result", "stat_finger"
    ]
    for table_name in table_list:
        try:
            conn_db(table_name).delete_many({'task_id': task_id})
        except Exception as e:
            logger.error(f"Error cleaning {table_name} for task {task_id}: {e}")
            
    # 清理遗留的截图文件，防止全量截图模式下撑爆磁盘
    import shutil
    from app.config import Config
    import os
    screenshot_path = os.path.join(Config.SCREENSHOT_DIR, task_id)
    if os.path.exists(screenshot_path):
        try:
            shutil.rmtree(screenshot_path, ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning screenshot dir for task {task_id}: {e}")

def safe_insert_asset(collection, unique_keys, item):
    """
    通用资产安全入库函数，防止重复数据。
    :param collection: 集合名，例如 'site', 'ip', 'domain'
    :param unique_keys: 唯一键列表，例如 ["task_id", "site"] 或者是更复杂的联合键
    :param item: 要插入的数据字典
    """
    if not item:
        return
    query = {}
    for k in unique_keys:
        val = item.get(k)
        if val is not None:
            query[k] = val
        else:
            # 对于嵌套字段(如 'port_info.port_id') 的支持 (简易版)
            if '.' in k:
                parts = k.split('.')
                curr = item
                for p in parts:
                    if isinstance(curr, dict):
                        curr = curr.get(p)
                    else:
                        curr = None
                        break
                if curr is not None:
                    query[k] = curr
                    
    from app.utils.monitor_diff import tag_monitor_diff
    tag_monitor_diff(collection, item)
                    
    if item.get("change_status") == "unchanged":
        return
        
    # 如果没凑齐 unique_keys，就直接退化成 insert_one（这种情况应该属于脏数据或特殊表）
    if not query or len(query) != len(unique_keys):
        conn_db(collection).insert_one(item)
    else:
        conn_db(collection).update_one(query, {"$set": item}, upsert=True)


from pymongo import UpdateOne
def safe_insert_asset_many(collection, unique_keys, items):
    """
    通用资产安全批量入库函数，防止重复数据且提升性能。
    :param collection: 集合名
    :param unique_keys: 唯一键列表
    :param items: 要插入的数据字典列表
    """
    if not items:
        return
        
    from app.utils.monitor_diff import tag_monitor_diff
    for item in items:
        tag_monitor_diff(collection, item)
    
    items = [item for item in items if item.get("change_status") != "unchanged"]
    if not items:
        return
    
    operations = []
    insert_items = []
    
    for item in items:
        query = {}
        for k in unique_keys:
            val = item.get(k)
            if val is not None:
                query[k] = val
            else:
                if '.' in k:
                    parts = k.split('.')
                    curr = item
                    for p in parts:
                        if isinstance(curr, dict):
                            curr = curr.get(p)
                        else:
                            curr = None
                            break
                    if curr is not None:
                        query[k] = curr
                        
        if not query or len(query) != len(unique_keys):
            insert_items.append(item)
        else:
            operations.append(UpdateOne(query, {"$set": item}, upsert=True))
            
    if insert_items:
        conn_db(collection).insert_many(insert_items)
        
    if operations:
        # 分批写入，防止数据包过大
        batch_size = 1000
        for i in range(0, len(operations), batch_size):
            conn_db(collection).bulk_write(operations[i:i+batch_size], ordered=False)
