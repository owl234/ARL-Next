import requests
from app import utils
from bson import ObjectId
from app.modules import TaskStatus
import time

logger = utils.get_logger()

def run_icp_task(options):
    task_id = options.get("task_id")
    target = options.get("target")
    query_types = options.get("query_type", ["web"])
    if isinstance(query_types, str):
        query_types = [query_types]
    
    # 1. 更新任务状态为进行中
    query = {"_id": ObjectId(task_id)}
    update_data = {"$set": {"status": TaskStatus.DONE, "start_time": utils.curr_date()}} # 将状态初始化，稍后更新
    utils.conn_db('icp_task').update_one(query, {"$set": {"status": "running"}})
    
    total_assets = 0
    error_msg = []
    counts = {"web": 0, "app": 0, "mapp": 0, "kapp": 0}
    
    for qt in query_types:
        url = f"http://icp_query:16181/query/{qt}?search={target}"
        logger.info(f"Start ICP query for {target} on {url}")
        
        try:
            response = requests.get(url, timeout=30)
            data = response.json()
            
            if data.get("code") == 200:
                params = data.get("params", {})
                asset_list = params.get("list", []) if isinstance(params, dict) else params
                
                # 3. 存储资产
                if asset_list and isinstance(asset_list, list):
                    for item in asset_list:
                        item['task_id'] = task_id
                        item['query_type'] = qt
                        utils.conn_db('icp_asset').insert_one(item)
                    total_assets += len(asset_list)
                    if qt in counts:
                        counts[qt] = len(asset_list)
            else:
                msg = data.get("msg", "Unknown error")
                error_msg.append(f"[{qt}] {msg}")
                logger.error(f"ICP Query error for {qt}: {data}")
                
        except Exception as e:
            logger.error(f"ICP Query exception for {qt}: {e}")
            error_msg.append(f"[{qt}] {str(e)}")
            
    # 4. 更新任务状态和统计
    if error_msg and total_assets == 0:
        # 全部失败
        update_data = {
            "$set": {
                "status": TaskStatus.ERROR, 
                "end_time": utils.curr_date(),
                "error_msg": "; ".join(error_msg),
                "statistic": {
                    "asset_cnt": 0,
                    "web_cnt": 0,
                    "app_cnt": 0,
                    "mapp_cnt": 0,
                    "kapp_cnt": 0
                }
            }
        }
    else:
        # 成功或部分成功
        update_data = {
            "$set": {
                "status": TaskStatus.DONE, 
                "end_time": utils.curr_date(),
                "statistic": {
                    "asset_cnt": total_assets,
                    "web_cnt": counts["web"],
                    "app_cnt": counts["app"],
                    "mapp_cnt": counts["mapp"],
                    "kapp_cnt": counts["kapp"]
                }
            }
        }
        if error_msg:
            update_data["$set"]["error_msg"] = "; ".join(error_msg)
            
    utils.conn_db('icp_task').update_one(query, update_data)
    logger.info(f"ICP query task {task_id} completed.")
