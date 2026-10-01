# backend/app/utils/db.py
"""通用数据库操作工具"""

from datetime import datetime
from bson import ObjectId

from app import utils
from app.utils.conn import conn_db

logger = utils.get_logger()

_INDEX_FLAGS = set()


def ensure_indexes(collection_name, indexes, db=None):
    """幂等创建索引"""
    flag = collection_name
    if flag in _INDEX_FLAGS:
        return
    try:
        # ★ 用 conn_db(name)，不用 db[name]
        coll = conn_db(collection_name)
        if indexes:
            coll.create_indexes(indexes)
            _INDEX_FLAGS.add(flag)
            logger.info("索引就绪: {}".format(collection_name))
    except Exception as e:
        logger.warning("索引创建异常 [{}]: {}".format(
            collection_name, e))


# 下面所有函数同理，全部用 conn_db(name)
def find_one(collection_name, query, projection=None, db=None):
    return conn_db(collection_name).find_one(query, projection)


def find_many(collection_name, query=None, projection=None,
              sort=None, skip=0, limit=0, db=None):
    coll = conn_db(collection_name)
    cursor = coll.find(query or {}, projection)
    if sort:
        cursor = cursor.sort(sort)
    if skip:
        cursor = cursor.skip(skip)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def find_paged(collection_name, query=None, projection=None,
               sort=None, page=1, page_size=20, db=None):
    coll = conn_db(collection_name)
    query = query or {}
    sort = sort or [("_id", -1)]
    total = coll.count_documents(query)
    cursor = (coll.find(query, projection)
              .sort(sort)
              .skip((page - 1) * page_size)
              .limit(page_size))
    return {"total": total, "page": page,
            "page_size": page_size, "items": list(cursor)}


def count(collection_name, query=None, db=None):
    return conn_db(collection_name).count_documents(query or {})


def insert_one(collection_name, document, db=None):
    return conn_db(collection_name).insert_one(document).inserted_id


def upsert_one(collection_name, query, insert_doc,
               update_doc=None, db=None):
    coll = conn_db(collection_name)
    existing = coll.find_one(query, {"_id": 1})
    if existing:
        update_fields = update_doc if update_doc is not None \
            else insert_doc
        if update_fields:
            coll.update_one(query, {"$set": update_fields})
        return False, existing["_id"]
    try:
        result = coll.insert_one(insert_doc)
        return True, result.inserted_id
    except Exception as e:
        logger.warning("upsert 冲突 [{}]: {}".format(
            collection_name, e))
        existing = coll.find_one(query, {"_id": 1})
        if existing:
            return False, existing["_id"]
        raise


def update_one(collection_name, query, update_fields,
               upsert=False, db=None):
    coll = conn_db(collection_name)
    result = coll.update_one(
        query, {"$set": update_fields}, upsert=upsert)
    return result.modified_count, result.upserted_id


def update_many(collection_name, query, update_fields, db=None):
    result = conn_db(collection_name).update_many(
        query, {"$set": update_fields})
    return result.modified_count


def delete_one(collection_name, query, db=None):
    return conn_db(collection_name).delete_one(query).deleted_count


def delete_many(collection_name, query, db=None):
    return conn_db(collection_name).delete_many(query).deleted_count


def delete_by_ids(collection_name, ids, db=None):
    coll = conn_db(collection_name)
    oids = []
    for _id in ids:
        try:
            oids.append(ObjectId(_id))
        except Exception:
            continue
    if not oids:
        return 0
    return coll.delete_many(
        {"_id": {"$in": oids}}).deleted_count