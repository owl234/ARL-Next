from app.utils.conn import conn_db

def get_performance_config():
    doc = conn_db('system_config').find_one({"_id": "performance"})
    if not doc:
        return 2  # Default celery concurrency
    return doc.get("celery_concurrency", 2)

def update_performance_config(celery_concurrency):
    conn_db('system_config').update_one(
        {"_id": "performance"}, 
        {"$set": {"celery_concurrency": celery_concurrency}}, 
        upsert=True
    )
