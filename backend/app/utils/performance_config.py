from app.utils.conn import conn_db

def get_performance_config():
    doc = conn_db('system_config').find_one({"_id": "performance"})
    if not doc:
        return {"celery_heavy_concurrency": 1, "celery_light_concurrency": 1, "osint_concurrency": 1}
    return {
        "celery_heavy_concurrency": doc.get("celery_heavy_concurrency", 1),
        "celery_light_concurrency": doc.get("celery_light_concurrency", 1),
        "osint_concurrency": doc.get("osint_concurrency", 1)
    }

def update_performance_config(celery_heavy_concurrency, celery_light_concurrency, osint_concurrency):
    conn_db('system_config').update_one(
        {"_id": "performance"}, 
        {"$set": {
            "celery_heavy_concurrency": celery_heavy_concurrency,
            "celery_light_concurrency": celery_light_concurrency,
            "osint_concurrency": osint_concurrency
        }}, 
        upsert=True
    )
