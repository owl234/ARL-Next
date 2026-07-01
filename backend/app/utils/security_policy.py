from app.utils.conn import conn_db
from app.config import Config
import time

_cache = {
    "black_ips": None,
    "forbidden_domains": None,
    "last_update": 0
}
CACHE_TTL = 60  # Cache for 60 seconds

def get_security_policy():
    now = time.time()
    if _cache["last_update"] > 0 and now - _cache["last_update"] < CACHE_TTL:
        return _cache["black_ips"], _cache["forbidden_domains"]
        
    doc = conn_db('system_config').find_one({"_id": "security_policy"})
    if not doc:
        black_ips = Config.BLACK_IPS
        forbidden_domains = Config.FORBIDDEN_DOMAINS
        # Seeding database with initial config
        conn_db('system_config').insert_one({
            "_id": "security_policy",
            "black_ips": black_ips,
            "forbidden_domains": forbidden_domains
        })
    else:
        black_ips = doc.get("black_ips", Config.BLACK_IPS)
        forbidden_domains = doc.get("forbidden_domains", Config.FORBIDDEN_DOMAINS)
        
    _cache["black_ips"] = black_ips
    _cache["forbidden_domains"] = forbidden_domains
    _cache["last_update"] = now
    
    return black_ips, forbidden_domains

def update_security_policy(black_ips, forbidden_domains):
    doc = {
        "black_ips": black_ips,
        "forbidden_domains": forbidden_domains
    }
    conn_db('system_config').update_one(
        {"_id": "security_policy"}, 
        {"$set": doc}, 
        upsert=True
    )
    # Immediately invalidate cache
    _cache["last_update"] = 0
