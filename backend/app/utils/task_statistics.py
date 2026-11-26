"""状态统计只读取分组数量，不加载任务记录或补算资产数据。"""

TERMINAL_TASK_STATUSES = ('done', 'stop', 'error')

CORE_ASSET_DIMENSION_FIELDS = {
    'site': 'statistic.site_cnt',
    'domain': 'statistic.domain_cnt',
    'ip': 'statistic.ip_cnt',
    'wih': 'statistic.wih_cnt',
    'vuln': 'statistic.vuln_cnt',
    'nuclei': 'statistic.nuclei_result_cnt',
}


def get_task_statistics(collection, include_stage_statuses=False):
    counts = {key: 0 for key in ('total', 'running', 'waiting', 'done', 'error', 'stop')}
    groups = collection.aggregate([{'$group': {'_id': '$status', 'count': {'$sum': 1}}}])
    for group in groups:
        status, count = group['_id'], group['count']
        counts['total'] += count
        if status in ('waiting', 'done', 'error', 'stop'):
            counts[status] += count
        elif status == 'running' or include_stage_statuses:
            counts['running'] += count
    counts['active'] = counts['running'] + counts['waiting']
    counts['abnormal'] = counts['error'] + counts['stop']
    return counts


def attach_task_statistics(data, collection, logger, include_stage_statuses=False):
    try:
        data['statistics'] = get_task_statistics(collection, include_stage_statuses)
    except Exception:
        logger.exception('Failed to aggregate task status statistics')
        # 列表仍可用；不以零值覆盖客户端已显示的统计。
        data['statistics_error'] = True
    return data


TASK_STATISTIC_TABLES = (
    'site', 'domain', 'ip', 'cert', 'service', 'fileleak',
    'url', 'vuln', 'npoc_service', 'cip',
    'nuclei_result', 'stat_finger', 'wih',
)


def flush_task_statistic_safely(task_id, logger=None, conn_db_fn=None):
    """在停止/异常等终态路径容错回写 task.statistic，不阻断主流程状态流转。"""
    if not task_id:
        return None
    try:
        from bson import ObjectId
        tid = str(task_id)
        if not ObjectId.is_valid(tid):
            return None
        from app import utils
        db_fn = conn_db_fn or utils.conn_db
        if conn_db_fn is not None:
            query = {'task_id': tid}
            stat = {f'{table}_cnt': db_fn(table).count_documents(query) for table in TASK_STATISTIC_TABLES}
        else:
            stat = utils.arl.task_statistic(tid)
        db_fn('task').update_one({'_id': ObjectId(tid)}, {'$set': {'statistic': stat}})
        return stat
    except Exception as exc:
        if logger is not None:
            logger.warning(f'Failed to flush task statistic for {task_id}: {exc}')
        return None
