"""普通扫描与手动同步共用的资产组校验和状态反馈。"""
from bson import ObjectId
from app import utils
from app.modules import ScopeValidationError, TaskSyncStatus
from app.helpers.scope import validate_task_scope


def sync_task_to_scope(task_id, scope_id, push_flag=False):
    # 此处只同步已有扫描结果，不重新派发扫描任务。
    from app.services.syncAsset import sync_asset
    tasks = utils.conn_db('task')
    query = {"_id": ObjectId(task_id)}
    task = tasks.find_one(query)
    if not task:
        return False
    try:
        scope = validate_task_scope(task.get("target", ""), scope_id)
        scope_id = str(scope["_id"])
        tasks.update_one(query, {"$set": {
            "sync_status": TaskSyncStatus.RUNNING, "sync_scope_id": scope_id,
            "sync_scope_name": scope.get("name", "")
        }, "$unset": {"sync_error": "", "sync_summary": ""}})
        sync_asset(task_id=task_id, scope_id=scope_id, push_flag=push_flag)
        tasks.update_one(query, {"$set": {
            "sync_status": TaskSyncStatus.DEFAULT, "synced_scope_id": scope_id,
            "synced_scope_name": scope.get("name", "")
        }, "$unset": {"sync_error": ""}})
        return True
    except ScopeValidationError as e:
        # 范围校验失败属可控失败：如实记录原因，不打异常栈误报为执行异常。
        tasks.update_one(query, {"$set": {"sync_status": TaskSyncStatus.ERROR, "sync_error": str(e)}})
        utils.get_logger().warning("task asset sync rejected(%s): %s", e.reason, task_id)
        return False
    except Exception as e:
        # 框架级异常（超时、WorkerLost、软超时等）才按异常上报。
        tasks.update_one(query, {"$set": {"sync_status": TaskSyncStatus.ERROR, "sync_error": str(e)}})
        utils.get_logger().exception("task asset sync failed: %s", task_id)
        return False
