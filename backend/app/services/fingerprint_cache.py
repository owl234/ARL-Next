from .fingerprint import FingerPrint
from app.utils import get_logger, conn_db, load_file, curr_date_obj
import threading
import time
import json
from pymongo.errors import BulkWriteError
from app.config import Config

logger = get_logger()

_FINGERPRINT_INIT_SENTINEL_ID = "fingerprint_initialized_v1"
_FINGERPRINT_CACHE_VERSION_ID = "_fingerprint_cache_version"


def is_fingerprint_initialized() -> bool:
    """检查指纹库是否已完成首次初始化。"""
    try:
        doc = conn_db('system_config').find_one({"_id": _FINGERPRINT_INIT_SENTINEL_ID})
        if doc and doc.get("initialized"):
            return True
    except Exception:
        pass
    return False


def mark_fingerprint_initialized(raise_on_error: bool = False):
    """持久化标记指纹库已完成首次初始化，避免用户删空后自动重灌。"""
    try:
        res = conn_db('system_config').update_one(
            {"_id": _FINGERPRINT_INIT_SENTINEL_ID},
            {"$set": {"initialized": True, "updated_at": time.time()}},
            upsert=True
        )
        if res is not None and getattr(res, "acknowledged", True) is False:
            raise RuntimeError("system_config update_one was not acknowledged")
    except Exception as e:
        if raise_on_error:
            raise
        logger.warning(f"Failed to mark fingerprint initialized: {e}")


def bump_fingerprint_cache_version():
    """递增指纹规则库跨进程版本号，使所有 Worker 进程的下一次读取都回源数据库。"""
    try:
        conn_db('system_config').update_one(
            {"_id": _FINGERPRINT_CACHE_VERSION_ID},
            {"$inc": {"version": 1}},
            upsert=True
        )
    except Exception as e:
        logger.warning(f"Failed to bump fingerprint cache version: {e}")


def _read_fingerprint_cache_version():
    """读取当前指纹缓存版本号；读取失败返回 None（不误触发失效）。"""
    try:
        doc = conn_db('system_config').find_one({"_id": _FINGERPRINT_CACHE_VERSION_ID})
        if doc:
            return doc.get("version")
    except Exception:
        pass
    return None


# 用于缓存指纹数据，避免每次请求都从MongoDB中获取数据
class FingerPrintCache:
    def __init__(self):
        self.cache = None
        self.last_update_time = 0
        self.cache_ttl = 60  # seconds
        self.cache_version = None
        self._lock = threading.RLock()

        self.ac_body = None
        self.ac_header = None
        self.ac_title = None
        self.has_ahocorasick = False
        try:
            import ahocorasick
            self.has_ahocorasick = True
        except ImportError:
            pass

    def _is_version_stale(self) -> bool:
        current_version = _read_fingerprint_cache_version()
        return current_version is not None and self.cache_version != current_version

    def is_cache_valid(self):
        return self.cache is not None and not self._is_version_stale()

    def invalidate_cache(self, bump_version: bool = True):
        """使当前进程缓存立即失效，并按需递增跨进程版本号。"""
        if bump_version:
            bump_fingerprint_cache_version()
        with self._lock:
            self.cache = None
            self.last_update_time = 0
            self.cache_version = None
            self.ac_body = None
            self.ac_header = None
            self.ac_title = None

    def get_data(self):
        with self._lock:
            if self.is_cache_valid():
                return self.cache

            # 如果缓存无效或版本过期，则重新从MongoDB中获取数据
            self.cache = self.fetch_data_from_mongodb()
            return self.cache

    def _auto_seed_if_empty(self):
        db = conn_db('fingerprint')
        if db.find_one({}, {"_id": 1}) is not None:
            return

        # 仅首次初始化且无删除黑名单记录时才允许自动灌入，防止用户删空指纹后复活
        if is_fingerprint_initialized():
            return
        if conn_db('fingerprint_deleted').find_one({}, {"_id": 1}) is not None:
            mark_fingerprint_initialized()
            return

        try:
            db.create_index("name", unique=True)
        except Exception as e:
            logger.warning(f"Failed to create unique index on fingerprint.name: {e}")

        logger.info("Fingerprint collection is empty and uninitialized. Auto-seeding from webapp.json...")
        try:
            web_app_rules = json.loads("\n".join(load_file(Config.web_app_rule)))
            deleted_names = set(conn_db('fingerprint_deleted').distinct('name'))
            docs = []
            for rule_name, rule_detail in web_app_rules.items():
                if rule_name not in deleted_names and "fofa_rule" in rule_detail and rule_detail["fofa_rule"]:
                    docs.append({
                        "name": rule_name,
                        "human_rule": rule_detail["fofa_rule"],
                        "update_date": curr_date_obj()
                    })
            if docs:
                db.insert_many(docs, ordered=False)
                logger.info(f"Successfully seeded {len(docs)} fingerprints.")
            mark_fingerprint_initialized()
        except BulkWriteError:
            logger.info("Auto-seed concurrency detected: duplicate fingerprints safely ignored.")
            mark_fingerprint_initialized()
        except Exception as e:
            logger.error(f"Failed to auto-seed fingerprints: {e}")

    def _build_ac_automata(self, finger_list):
        if not self.has_ahocorasick:
            return

        fields = ('body', 'header', 'title')
        if not finger_list:
            for key in fields:
                setattr(self, f'ac_{key}', None)
            return

        import ahocorasick
        trees = {key: ahocorasick.Automaton() for key in fields}
        counts = {key: 0 for key in fields}

        for finger in finger_list:
            if finger.parsed is None:
                finger.build_parsed()

            for key in fields:
                for word in finger.literals[key]:
                    w = word.lower()
                    trees[key].add_word(w, w)
                    counts[key] += 1

        for key in fields:
            if counts[key] > 0:
                trees[key].make_automaton()
                setattr(self, f'ac_{key}', trees[key])
            else:
                setattr(self, f'ac_{key}', None)

    def fetch_data_from_mongodb(self) -> [FingerPrint]:
        self._auto_seed_if_empty()
        # 先读取版本号再查数据，避免并发更新时把旧数据绑定到新版本号
        current_version = _read_fingerprint_cache_version()
        items = list(conn_db('fingerprint').find())
        finger_list = []
        for rule in items:
            finger = FingerPrint(rule['name'], rule['human_rule'])
            finger_list.append(finger)

        try:
            self._build_ac_automata(finger_list)
        except Exception as e:
            logger.error(f"Failed to build AC Automata: {e}")
            self.has_ahocorasick = False

        self.last_update_time = time.time()
        self.cache_version = current_version
        return finger_list

    def update_cache(self, force=False):
        # 手动更新缓存，带TTL防止高并发启动时频繁查库；若跨进程版本号变更则立即失效重载
        with self._lock:
            if (force or self.cache is None or self._is_version_stale()
                    or (time.time() - self.last_update_time > self.cache_ttl)):
                self.cache = self.fetch_data_from_mongodb()


finger_db_cache = FingerPrintCache()


def finger_db_identify(variables: dict) -> [str]:
    finger_list = finger_db_cache.get_data()
    finger_name_list = []

    matched_literals = {'body': set(), 'header': set(), 'title': set()}

    # 预先将文本字段统一转为小写，避免多规则重复调用 .lower()，提升匹配效率并保证大小写不敏感
    scan_vars = {
        'body': variables.get('body', '').lower() if isinstance(variables.get('body'), str) else '',
        'header': variables.get('header', '').lower() if isinstance(variables.get('header'), str) else '',
        'title': variables.get('title', '').lower() if isinstance(variables.get('title'), str) else ''
    }

    if finger_db_cache.has_ahocorasick:
        # scan using AC
        for key, ac_tree in [('body', finger_db_cache.ac_body), 
                             ('header', finger_db_cache.ac_header), 
                             ('title', finger_db_cache.ac_title)]:
            text = scan_vars[key]
            if text and ac_tree is not None:
                try:
                    for end_index, original_value in ac_tree.iter(text):
                        matched_literals[key].add(original_value)
                except Exception:
                    pass

    # 将已转小写的文本变量与原始变量（如 icon_hash）合并用于求值
    eval_vars = dict(variables)
    eval_vars.update(scan_vars)

    for finger in finger_list:
        try:
            if finger_db_cache.has_ahocorasick and not finger.has_not_or_regex:
                has_any_literals = False
                found_any_match = False
                
                for key in ['body', 'header', 'title']:
                    if finger.literals[key]:
                        has_any_literals = True
                        if finger.literals[key] & matched_literals[key]:
                            found_any_match = True
                            break
                            
                if has_any_literals and not found_any_match:
                    continue  # Short circuit!

            if finger.identify(eval_vars):
                finger_name_list.append(finger.app_name)
        except Exception as e:
            logger.warning("error on identify {} {}".format(finger.app_name, e))

    return finger_name_list

def have_human_rule_from_db(rule: str) -> bool:
    query = {
        "human_rule": rule,
    }

    if conn_db('fingerprint').find_one(query):
        return True
    else:
        return False


