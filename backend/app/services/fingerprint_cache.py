from .fingerprint import FingerPrint
from app.utils import get_logger, conn_db, load_file, curr_date_obj
import time
import json
from pymongo.errors import BulkWriteError
from app.config import Config

logger = get_logger()


# 用于缓存指纹数据，避免每次请求都从MongoDB中获取数据
class FingerPrintCache:
    def __init__(self):
        self.cache = None
        self.last_update_time = 0
        self.cache_ttl = 60  # seconds
        
        self.ac_body = None
        self.ac_header = None
        self.ac_title = None
        self.has_ahocorasick = False
        try:
            import ahocorasick
            self.has_ahocorasick = True
        except ImportError:
            pass

    def is_cache_valid(self):
        return self.cache is not None

    def get_data(self):
        if self.is_cache_valid():
            return self.cache

        # 如果缓存无效，则重新从MongoDB中获取数据
        self.cache = self.fetch_data_from_mongodb()
        return self.cache

    def _auto_seed_if_empty(self):
        db = conn_db('fingerprint')
        db.create_index("name", unique=True)
        if db.count_documents({}) == 0:
            logger.info("Fingerprint collection is empty. Auto-seeding from webapp.json...")
            try:
                web_app_rules = json.loads("\n".join(load_file(Config.web_app_rule)))
                docs = []
                for rule_name, rule_detail in web_app_rules.items():
                    if "fofa_rule" in rule_detail and rule_detail["fofa_rule"]:
                        docs.append({
                            "name": rule_name,
                            "human_rule": rule_detail["fofa_rule"],
                            "update_date": curr_date_obj()
                        })
                if docs:
                    db.insert_many(docs, ordered=False)
                    logger.info(f"Successfully seeded {len(docs)} fingerprints.")
            except BulkWriteError:
                logger.info("Auto-seed concurrency detected: duplicate fingerprints safely ignored.")
            except Exception as e:
                logger.error(f"Failed to auto-seed fingerprints: {e}")

    def _build_ac_automata(self, finger_list):
        if not self.has_ahocorasick:
            return
            
        import ahocorasick
        self.ac_body = ahocorasick.Automaton()
        self.ac_header = ahocorasick.Automaton()
        self.ac_title = ahocorasick.Automaton()
        
        for finger in finger_list:
            if finger.parsed is None:
                finger.build_parsed()
                
            for word in finger.literals['body']:
                w = word.lower()
                self.ac_body.add_word(w, w)
            for word in finger.literals['header']:
                w = word.lower()
                self.ac_header.add_word(w, w)
            for word in finger.literals['title']:
                w = word.lower()
                self.ac_title.add_word(w, w)
                
        self.ac_body.make_automaton()
        self.ac_header.make_automaton()
        self.ac_title.make_automaton()

    def fetch_data_from_mongodb(self) -> [FingerPrint]:
        self._auto_seed_if_empty()
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
        return finger_list

    def update_cache(self, force=False):
        # 手动更新缓存，带TTL防止高并发启动时频繁查库
        if force or self.cache is None or (time.time() - self.last_update_time > self.cache_ttl):
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
            if text:
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


