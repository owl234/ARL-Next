import datetime
import re
import time
from lxml import etree
from app import utils
from app.config import Config
from app.modules import CeleryAction
from app.utils.push import unified_push

logger = utils.get_logger()


def get_github_headers():
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    if Config.GITHUB_TOKEN:
        headers['Authorization'] = f"token {Config.GITHUB_TOKEN}"
    return headers


class ThreatIntelligencePush:
    @staticmethod
    def push_msg(title, body):
        if 'CVE' in title:
            push_type = 'github_cve'
        elif '工具' in title or '监控' in title:
            push_type = 'github_tools'
        elif '大佬' in title or '动态' in title:
            push_type = 'github_hackers'
        else:
            push_type = 'github_leak'
            
        unified_push(push_type, title, body)


class GithubCveMonitorTask:
    def __init__(self):
        self.collection = "github_cve_history"
        
    def fetch_mitre_cve_desc(self, cve_id, default_desc=""):
        try:
            url = f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}"
            res = utils.http_req(url, timeout=(3, 5), proxy_domain="intel")
            if res and res.text:
                html = etree.HTML(res.text)
                if html is not None:
                    elements = html.xpath('//*[@id="GeneratedTable"]/table//tr[4]/td/text()')
                    if elements:
                        des = elements[0].strip()
                        if des:
                            return des
        except Exception as e:
            logger.warning(f"Fetch MITRE desc failed for {cve_id}: {e}")
        return default_desc if default_desc else "No description available on MITRE yet."

    def run(self):
        logger.info("Starting Github CVE Monitor Task...")
        year = datetime.datetime.now().year
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        api = f"https://api.github.com/search/repositories?q=CVE-{year}&sort=updated&per_page=100"
        
        try:
            res = utils.http_req(api, headers=get_github_headers(), timeout=(10, 10), proxy_domain="intel")
            if not res:
                logger.error("Failed to fetch Github repos for CVE: network error or empty response.")
                return

            if res.status_code in (403, 429):
                logger.error(f"GitHub API Rate Limit hit ({res.status_code}) while searching CVEs. Halting scan.")
                return

            if res.status_code != 200:
                logger.error(f"Failed to fetch Github repos for CVE, status code: {res.status_code}")
                return

            items = res.json().get('items', [])[:100]
            db = utils.conn_db(self.collection)

            for item in items:
                cve_name_raw = item.get('name', '').upper()
                cve_match = re.findall(r'(CVE-\d+-\d+)', cve_name_raw)
                if not cve_match:
                    continue
                    
                cve_id = cve_match[0]
                pushed_at_str = item.get('pushed_at', '')
                try:
                    pushed_at_dt = datetime.datetime.strptime(pushed_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                    # 转换为北京时间 (UTC+8) 存入数据库
                    pushed_at_local_dt = pushed_at_dt + datetime.timedelta(hours=8)
                    pushed_at_date = pushed_at_local_dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
                repo_url = item.get('html_url', '')

                # 仅处理最近24小时内更新的仓库（解决跨时区问题）
                if (now_dt - pushed_at_dt).total_seconds() > 24 * 3600:
                    continue

                # 优先获取 GitHub 仓库自带 POC 描述作为即时内容与降级底包
                repo_desc = (item.get('description') or '').strip()

                # Use upsert to prevent race conditions
                result = db.update_one(
                    {"cve_name": cve_id},
                    {"$setOnInsert": {
                        "cve_name": cve_id,
                        "cve_url": repo_url,
                        "pushed_at": pushed_at_date,
                        "insert_time": utils.curr_date(),
                        "desc": repo_desc
                    }},
                    upsert=True
                )
                
                if result.upserted_id is not None:
                    logger.info(f"New CVE found: {cve_id}")
                    # 低延迟尝试拉取官方描述，失败自动降级为仓库原生描述
                    official_desc = self.fetch_mitre_cve_desc(cve_id, default_desc=repo_desc)
                    if official_desc and official_desc != repo_desc:
                        db.update_one({"_id": result.upserted_id}, {"$set": {"desc": official_desc}})
                        final_desc = official_desc
                    else:
                        final_desc = repo_desc or "暂无官方与仓库描述"
                    
                    title = f"🚨 发现新公开的 {cve_id} Github 利用代码！"
                    body = (
                        f"**CVE 编号**: {cve_id}\n"
                        f"**项目地址**: {repo_url}\n"
                        f"**官方/项目描述**: \n{final_desc}\n"
                    )
                    ThreatIntelligencePush.push_msg(title, body)
                
        except Exception as e:
            logger.exception(f"GithubCveMonitorTask Error: {e}")


class GithubToolsMonitorTask:
    def __init__(self):
        self.collection = "github_tools_target"

    def run(self):
        logger.info("Starting Github Tools Monitor Task...")
        db = utils.conn_db(self.collection)
        targets = list(db.find({})) 
        
        for target in targets:
            repo_url = target.get('repo_url')
            if not repo_url: continue
                
            try:
                api_releases = f"{repo_url}/releases"
                res = utils.http_req(api_releases, headers=get_github_headers(), timeout=(5, 10), proxy_domain="intel")

                if not res:
                    continue

                if res.status_code in (403, 429):
                    logger.warning(f"GitHub API rate limit hit ({res.status_code}) in Tools monitor, halting current scan.")
                    break
                
                if res.status_code == 200:
                    releases = res.json()
                    if isinstance(releases, list) and len(releases) > 0:
                        latest = releases[0]
                        new_tag = latest.get('tag_name', '')
                        try:
                            published_at_str = latest.get('published_at', '')
                            published_at_dt = datetime.datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                            published_at_local_dt = published_at_dt + datetime.timedelta(hours=8)
                            new_pushed_at = published_at_local_dt.strftime("%Y-%m-%d")
                        except Exception:
                            new_pushed_at = ""
                        
                        old_tag = target.get('last_tag', '')
                        release_notes = (latest.get('body') or '')[:4000]
                        release_url = latest.get('html_url') or ''
                        release_name = latest.get('name') or ''
                        needs_backfill = 'release_notes' not in target or 'release_url' not in target
                        if new_tag != old_tag or needs_backfill:
                            # Atomically update release metadata; push only on actual version bump
                            update_fields = {
                                "last_tag": new_tag,
                                "last_commit_time": new_pushed_at,
                                "release_url": release_url,
                                "release_name": release_name,
                                "release_notes": release_notes,
                            }
                            if new_tag != old_tag:
                                result = db.update_one(
                                    {"_id": target["_id"], "last_tag": old_tag},
                                    {"$set": update_fields}
                                )
                                if result.modified_count > 0 and old_tag != '':
                                    update_log = release_notes or 'No update log provided.'
                                    download_url = release_url
                                    tool_name = repo_url.split('/')[-1]
                                    
                                    title = f"🛠️ 工具 [{tool_name}] 发布了新版本: {new_tag}"
                                    body = f"**地址**: {download_url}\n**更新日志**:\n{update_log}"
                                    
                                    ThreatIntelligencePush.push_msg(title, body)
                            else:
                                db.update_one({"_id": target["_id"]}, {"$set": update_fields})
            except Exception as e:
                logger.error(f"Failed to check tool {repo_url}: {e}")


class GithubHackersMonitorTask:
    def __init__(self):
        self.collection = "github_hackers_target"
        self.history_collection = "github_hackers_history" # 记录推送过的仓库，避免重复
        
    def run(self):
        logger.info("Starting Github Hackers Monitor Task...")
        db = utils.conn_db(self.collection)
        history_db = utils.conn_db(self.history_collection)
        
        targets = list(db.find({}))
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        
        for target in targets:
            github_id = target.get('github_id')
            if not github_id: continue
                
            try:
                api = f"https://api.github.com/users/{github_id}/repos?sort=created&direction=desc"
                res = utils.http_req(api, headers=get_github_headers(), timeout=(5, 10), proxy_domain="intel")

                if not res:
                    continue

                if res.status_code in (403, 429):
                    logger.warning(f"GitHub API rate limit hit ({res.status_code}) when querying hacker {github_id}, halting scan.")
                    break
                
                if res.status_code != 200:
                    continue
                    
                repos = res.json()
                if not isinstance(repos, list):
                    continue

                for repo in repos:
                    # 避免遍历太多，只看最近几条
                    if isinstance(repo, dict):
                        fork = repo.get('fork', False)
                        created_at_raw = repo.get('created_at', '')
                        if not created_at_raw: continue
                        
                        try:
                            created_at_dt = datetime.datetime.strptime(created_at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            continue
                            
                        # 仅处理最近24小时内创建的仓库（解决时区导致的部分时段遗漏）
                        is_recent = (now_dt - created_at_dt).total_seconds() <= 24 * 3600
                        
                        if is_recent and not fork:
                            full_name = repo.get('full_name')
                            description = (repo.get('description') or '').strip()
                            download_url = repo.get('html_url') or f"https://github.com/{full_name}"
                            language = repo.get('language') or ''
                            stargazers_count = int(repo.get('stargazers_count') or 0)
                            created_local_str = (created_at_dt + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

                            # 检查是否已推送并原子插入
                            result = history_db.update_one(
                                {"full_name": full_name},
                                {"$setOnInsert": {
                                    "full_name": full_name,
                                    "owner": github_id,
                                    "html_url": download_url,
                                    "description": description,
                                    "language": language,
                                    "stargazers_count": stargazers_count,
                                    "created_at": created_local_str,
                                    "insert_time": utils.curr_date()
                                }},
                                upsert=True
                            )
                            
                            if result.upserted_id is not None:
                                name = repo.get('name')
                                push_desc = description or "作者未写描述"
                                
                                title = f"👨‍💻 大佬 [{github_id}] 分享了一款新工具!"
                                body = (
                                    f"**工具名称**: {name}\n"
                                    f"**项目地址**: {download_url}\n"
                                    f"**工具描述**: {push_desc}\n"
                                )
                                ThreatIntelligencePush.push_msg(title, body)
            except Exception as e:
                logger.error(f"Failed to check hacker {github_id}: {e}")


THREAT_CONFIG_MAP = {
    "cve": {
        "config_id": "cve_radar_config",
        "action": CeleryAction.GITHUB_THREAT_CVE,
        "task_cls": GithubCveMonitorTask,
        "name": "CVE 威胁情报监控"
    },
    "tools": {
        "config_id": "tools_radar_config",
        "action": CeleryAction.GITHUB_THREAT_TOOLS,
        "task_cls": GithubToolsMonitorTask,
        "name": "安全工具更新监控"
    },
    "hackers": {
        "config_id": "hackers_radar_config",
        "action": CeleryAction.GITHUB_THREAT_HACKERS,
        "task_cls": GithubHackersMonitorTask,
        "name": "黑客大牛动态监控"
    }
}

LOCK_TIMEOUT_SECONDS = 1800  # 30 分钟超时自愈


def dispatch_threat_task(task_type: str, force: bool = False):
    """
    非阻塞调度派发：通过 MongoDB CAS 锁防重，并将任务投递至 Celery arlgithub 异步队列
    """
    if task_type not in THREAT_CONFIG_MAP:
        return False, f"未知的威胁情报类型: {task_type}"

    meta = THREAT_CONFIG_MAP[task_type]
    config_id = meta["config_id"]
    action = meta["action"]
    db = utils.conn_db("system_config")
    now = time.time()

    conf = db.find_one({"_id": config_id}) or {}
    is_running = conf.get("is_running", False)
    running_since = conf.get("running_since", 0)

    # 僵尸状态自愈检测：如果标记为 running 但已超时，自动释放
    if is_running and (now - running_since > LOCK_TIMEOUT_SECONDS):
        logger.warning(f"Threat task [{task_type}] exceeded lock window ({LOCK_TIMEOUT_SECONDS}s). Auto self-healing.")
        is_running = False

    if is_running and not force:
        return False, f"{meta['name']} 正在后台执行中，请勿重复调度"

    # CAS 原子占锁
    query = {
        "_id": config_id,
        "$or": [
            {"is_running": {"$ne": True}},
            {"running_since": {"$lt": now - LOCK_TIMEOUT_SECONDS}}
        ]
    }
    update = {
        "$set": {
            "is_running": True,
            "running_since": now,
            "last_run_time": now
        }
    }

    if force:
        db.update_one({"_id": config_id}, update, upsert=True)
        acquired = True
    else:
        if not conf:
            db.update_one({"_id": config_id}, {"$setOnInsert": {"enabled": False, "interval": 6}, **update}, upsert=True)
            acquired = True
        else:
            res = db.update_one(query, update)
            acquired = res.modified_count > 0

    if not acquired:
        return False, f"{meta['name']} 正在后台执行中，请稍后刷新"

    # 投递至 Celery arlgithub 异步队列
    try:
        from app import celerytask
        task_options = {
            "celery_action": action,
            "data": {
                "name": meta["name"],
                "task_type": task_type,
                "dispatch_time": now
            }
        }
        celery_res = celerytask.arl_github.delay(options=task_options)
        logger.info(f"Dispatched {meta['name']} to Celery arlgithub successfully (id: {celery_res.id})")
        return True, "任务已成功提交至 Celery 后台队列"
    except Exception as e:
        logger.exception(f"Failed to dispatch {meta['name']} to Celery: {e}")
        db.update_one({"_id": config_id}, {"$set": {"is_running": False}})
        return False, f"任务派发失败: {e}"


def run_threat_task_worker(task_type: str):
    """
    Celery Worker 实际执行体：运行监控并在结束后释放 is_running 锁
    """
    if task_type not in THREAT_CONFIG_MAP:
        logger.error(f"Unknown threat task_type in worker: {task_type}")
        return

    meta = THREAT_CONFIG_MAP[task_type]
    config_id = meta["config_id"]
    db = utils.conn_db("system_config")
    start_t = time.time()
    logger.info(f"Celery worker running threat task: {meta['name']}")

    try:
        task_instance = meta["task_cls"]()
        task_instance.run()
    except Exception as e:
        logger.exception(f"Unhandled error in {meta['name']}: {e}")
    finally:
        elapsed = time.time() - start_t
        logger.info(f"Completed {meta['name']}, elapsed: {elapsed:.2f}s. Releasing lock.")
        db.update_one({"_id": config_id}, {"$set": {"is_running": False, "last_finish_time": time.time()}})


def threat_intelligence_scheduler():
    """
    调度器轻量巡检：毫秒级判定周期并异步派发，严禁同步执行阻塞主循环
    """
    now = time.time()
    db = utils.conn_db("system_config")

    for task_type, meta in THREAT_CONFIG_MAP.items():
        try:
            config_id = meta["config_id"]
            conf = db.find_one({"_id": config_id}) or {"enabled": False, "interval": 6}
            if not conf.get("enabled", False):
                continue

            interval_hours = conf.get("interval", 6)
            last_run = conf.get("last_run_time", 0)
            if now - last_run > 3600 * interval_hours:
                success, msg = dispatch_threat_task(task_type)
                if success:
                    logger.info(f"[Scheduler] 成功触发定时调度: {meta['name']}")
                else:
                    logger.debug(f"[Scheduler] 跳过定时调度 {meta['name']}: {msg}")
        except Exception as e:
            logger.error(f"Threat intelligence schedule error for {task_type}: {e}")
