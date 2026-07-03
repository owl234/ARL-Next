import time
from app import utils
from bson import ObjectId
from app.modules import TaskStatus
from app.services.tycClient import TycClient, TycTokenExpiredException, TycRiskControlException

logger = utils.get_logger()

def run_tyc_task(options):
    task_id = options.get("task_id")
    gid = options.get("gid")
    depth = options.get("depth", 1)
    query_types = options.get("query_type", [])

    if isinstance(query_types, str):
        query_types = [query_types]

    query = {"_id": ObjectId(task_id)}
    # 初始化状态
    utils.conn_db('icp_task').update_one(query, {"$set": {"status": "running", "start_time": utils.curr_date()}})

    error_msg = []
    total_assets = 0
    counts = {qt: 0 for qt in query_types}

    try:
        client = TycClient()

        # 1. 递归查询获取所有的 GID 列表
        target_gids = {gid}
        current_level_gids = {gid}

        logger.info(f"[TYC TASK {task_id}] 开始查询投资层级，深度: {depth}")

        for level in range(depth):
            next_level_gids = set()
            for current_gid in current_level_gids:
                try:
                    invest_list = client.get_invest_list(current_gid)
                    if invest_list:
                        for item in invest_list:
                            sub_id = str(item.get("id", ""))
                            if sub_id and sub_id not in target_gids:
                                next_level_gids.add(sub_id)
                                target_gids.add(sub_id)
                except Exception as e:
                    logger.error(f"[TYC TASK] 获取 {current_gid} 投资列表失败: {e}")
                    error_msg.append(f"获取投资异常: {str(e)[:50]}")
            current_level_gids = next_level_gids
            if not next_level_gids:
                break

        logger.info(f"[TYC TASK {task_id}] 投资层级查询结束，共发现 {len(target_gids)} 个企业ID")

        # 2. 对每个公司执行 query_types 查询
        # query_types 包含: trademark, web, app, mapp, wechat, weibo, invest(如果前端也想要保存投资列表的话)
        # 资产保存到 icp_asset 表中

        for t_gid in target_gids:
            for qt in query_types:
                results = []
                try:
                    if qt == "invest":
                        results = client.get_invest_list(t_gid)
                    elif qt == "trademark":
                        results = client.get_trademark_list(t_gid)
                    elif qt == "web":
                        results = client.get_icp_record_list(t_gid)
                    elif qt == "mapp":
                        results = client.get_mini_program_list(t_gid)
                    elif qt == "app":
                        results1 = client.get_app_list(t_gid)
                        results2 = []
                        try:
                            results2 = client.get_app_icp_record_list(t_gid)
                        except Exception as inner_e:
                            logger.error(f"查询 app_icp_record_list 异常: {inner_e}")

                        # 合并去重 (以 APP 名称为基准)
                        merged_results = []
                        seen_names = set()
                        for item in results1 + results2:
                            name = item.get("name") or item.get("appName") or item.get("filterName") or item.get("serviceName")
                            if name and name not in seen_names:
                                seen_names.add(name)
                                item["name"] = name  # 确保前端统一使用 name 字段渲染
                                merged_results.append(item)
                        results = merged_results
                    elif qt == "wechat":
                        results = client.get_wechat_list(t_gid)
                    elif qt == "weibo":
                        results = client.get_weibo_list(t_gid)
                except TycTokenExpiredException as e:
                    error_msg.append("Token失效")
                    logger.error(f"Token 失效: {e}")
                    break # 跳出当前公司的查询
                except TycRiskControlException as e:
                    error_msg.append("触发风控")
                    logger.error(f"风控拦截: {e}")
                    break # 跳出当前公司的查询
                except Exception as e:
                    error_msg.append(f"查询 {qt} 异常")
                    logger.error(f"查询异常 {qt}: {e}")

                if results:
                    import re
                    for item in results:
                        item['task_id'] = task_id
                        item['query_type'] = qt
                        item['company_gid'] = t_gid # 记录归属的GID

                        # 解析注册资本和投资比例为纯数字，方便后续支持范围查询
                        if qt == 'invest':
                            if item.get('regCapital'):
                                match = re.search(r"(\d+(\.\d+)?)", str(item['regCapital']))
                                if match:
                                    item['regCapital_num'] = float(match.group(1))
                            if item.get('percent'):
                                match = re.search(r"(\d+(\.\d+)?)", str(item['percent']))
                                if match:
                                    item['percent_num'] = float(match.group(1))

                        utils.conn_db('icp_asset').insert_one(item)
                    total_assets += len(results)
                    counts[qt] += len(results)

        # 3. 如果所有查询类型都为空，删除任务
        if total_assets == 0 and not error_msg:
            logger.info(f"[TYC TASK {task_id}] 所有查询均为空，自动删除任务")
            utils.conn_db('icp_task').delete_one(query)
            return

    except Exception as e:
        logger.error(f"[TYC TASK {task_id}] 全局异常: {e}")
        error_msg.append(f"全局异常: {str(e)[:50]}")

    # 4. 更新任务状态和统计
    if error_msg and total_assets == 0:
        # 全部失败
        update_data = {
            "$set": {
                "status": TaskStatus.ERROR,
                "end_time": utils.curr_date(),
                "error_msg": "; ".join(list(set(error_msg))),
                "statistic": {
                    "asset_cnt": 0,
                    **{f"{k}_cnt": 0 for k in counts.keys()}
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
                    **{f"{k}_cnt": v for k, v in counts.items()}
                }
            }
        }
        if error_msg:
            update_data["$set"]["error_msg"] = "; ".join(list(set(error_msg)))

    utils.conn_db('icp_task').update_one(query, update_data)
    logger.info(f"[TYC TASK {task_id}] 任务执行完成，共计资产: {total_assets}")
