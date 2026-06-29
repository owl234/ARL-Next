from .fingerprint import FingerPrint
from app.utils import get_logger, conn_db, load_file, curr_date_obj
import time
import json
from app.config import Config

logger = get_logger()


# 用于缓存指纹数据，避免每次请求都从MongoDB中获取数据
class FingerPrintCache:
    def __init__(self):
        self.cache = None
        self.last_update_time = 0
        self.cache_ttl = 60  # seconds

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
                    db.insert_many(docs)
                    logger.info(f"Successfully seeded {len(docs)} fingerprints.")
            except Exception as e:
                logger.error(f"Failed to auto-seed fingerprints: {e}")

    def fetch_data_from_mongodb(self) -> [FingerPrint]:
        self._auto_seed_if_empty()
        items = list(conn_db('fingerprint').find())
        finger_list = []
        for rule in items:
            finger = FingerPrint(rule['name'], rule['human_rule'])
            finger_list.append(finger)

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

    for finger in finger_list:
        try:
            if finger.identify(variables):
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

