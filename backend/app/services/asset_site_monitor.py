import threading
from app.helpers import asset_site, asset_domain
from app import utils
from app.helpers.scope import get_scope_by_scope_id
from app.helpers.asset_site_monitor import is_black_asset_site
from .baseThread import BaseThread
from .fetchSite import fetch_site


logger = utils.get_logger()





class AssetSiteMonitor(object):
    def __init__(self, scope_id):
        self.scope_id = scope_id
        self.status_change_list = []
        self.title_change_list = []
        self.length_change_list = []
        self.site_change_info_list = []  # 保存变化了的站点信息，用于保存到任务中
        scope_data = get_scope_by_scope_id(self.scope_id)
        if not scope_data:
            raise Exception("没有找到资产组 {}".format(self.scope_id))

        self.scope_name = scope_data["name"]

    def compare_status(self, site_info, old_site_info):
        curr_status = site_info.get("status", 0)
        old_status = old_site_info.get("status", 0)
        curr_site = site_info["site"]

        if curr_status != old_status:
            item = {
                "site": curr_site,
                "status": curr_status,
                "old_status": old_status
            }
            logger.info("{} status {} => {}".format(curr_site, old_status, curr_status))

            self.status_change_list.append(item)
            return True
        return False

    def compare_title(self, site_info, old_site_info):
        curr_title = site_info.get("title", "")
        old_title = old_site_info.get("title", "")
        curr_site = site_info["site"]

        if curr_title != old_title:
            item = {
                "site": curr_site,
                "title": curr_title,
                "old_title": old_title
            }

            logger.info("{} title {} => {}".format(curr_site, old_title, curr_title))

            self.title_change_list.append(item)
            return True
        return False

    def compare_simhash(self, site_info, old_site_info):
        curr_simhash = site_info.get("simhash", "")
        old_simhash = old_site_info.get("simhash", "")
        curr_site = site_info["site"]
        
        # 兼容旧数据没有 simhash 的情况，如果没有则回退比较长度
        if not old_simhash:
            return self.compare_length(site_info, old_site_info)

        if curr_simhash and old_simhash and curr_simhash != old_simhash:
            # 也可以计算 Hamming Distance，这里简单判断如果不等则有变动
            # Simhash 设计使得即使局部不同，hash 也有差异，完全相等代表整体结构未变
            import simhash
            try:
                distance = simhash.Simhash(int(curr_simhash)).distance(simhash.Simhash(int(old_simhash)))
            except Exception:
                distance = 0
            
            # 距离大于3，认为页面发生了实质性改变
            if distance > 3:
                item = {
                    "site": curr_site,
                    "length": site_info.get("body_length", 0),
                    "old_length": old_site_info.get("body_length", 0),
                    "distance": distance
                }
                logger.info("{} simhash distance {} => changed".format(curr_site, distance))
                self.length_change_list.append(item)
                return True
        return False

    def compare_length(self, site_info, old_site_info):
        curr_length = site_info.get("body_length", 0)
        old_length = old_site_info.get("body_length", 0)
        curr_site = site_info["site"]

        if old_length > 0 and curr_length > 0:
            diff = abs(curr_length - old_length)
            # 引入绝对阈值，避免动态页面极小变动导致的误报
            if diff > 500 and diff / old_length > 0.05:
                item = {
                    "site": curr_site,
                    "length": curr_length,
                    "old_length": old_length,
                    "distance": -1
                }
                logger.info("{} length {} => {}".format(curr_site, old_length, curr_length))
                self.length_change_list.append(item)
                return True
        return False

    def build_change_list(self):
        # 1. 从数据库获取该 scope 下的所有站点信息游标
        old_site_cursor = asset_site.find_site_info_by_scope_id(scope_id=self.scope_id)
        if not old_site_cursor:
            logger.info("not found old sites, scope_id: {}".format(self.scope_id))
            return

        from pymongo import UpdateOne
        batch_size = 500
        curr_date = utils.curr_date_obj()
        
        batch = []
        total_count = 0
        for site_doc in old_site_cursor:
            batch.append(site_doc)
            total_count += 1
            if len(batch) >= batch_size:
                self._process_site_batch(batch, curr_date)
                batch = []
                
        if batch:
            self._process_site_batch(batch, curr_date)
            
        logger.info("processed total scope site {}, scope_id: {}".format(total_count, self.scope_id))

    def _process_site_batch(self, batch_docs, curr_date):
        old_site_map = {item["site"]: item for item in batch_docs}
        sites = list(old_site_map.keys())

        # 2. 发起批量请求
        new_site_infos = fetch_site(sites)
        
        from pymongo import UpdateOne
        bulk_updates = []

        for site_info in new_site_infos:
            curr_site = site_info["site"]
            if curr_site not in old_site_map:
                continue

            old_site_info = old_site_map[curr_site]
            
            is_entry = "入口" in site_info.get("tag", [])
            was_entry = "入口" in old_site_info.get("tag", [])

            # --- 修复后的防抖逻辑 ---
            curr_status = site_info.get("status", 0)
            # 仅针对网络波动/网关错误进行防抖 (0: 超时/无法解析, 502/503/504: 网关错误)
            if curr_status in [0, 502, 503, 504]:
                tolerance_limit = 2 if (is_entry or was_entry) else 3
                current_count = old_site_info.get("consecutive_error_count", 0) + 1
                site_info["consecutive_error_count"] = current_count
                
                if current_count < tolerance_limit:
                    # 挂起告警，仅更新计数器
                    bulk_updates.append(UpdateOne(
                        {"_id": old_site_info["_id"]},
                        {"$set": {"consecutive_error_count": current_count}}
                    ))
                    continue
            else:
                site_info["consecutive_error_count"] = 0
            # ------------------------

            changed = False
            
            # 不再对比无效标题
            if site_info.get("title") and self.compare_title(site_info, old_site_info):
                changed = True

            if self.compare_status(site_info, old_site_info):
                changed = True

            if self.compare_simhash(site_info, old_site_info):
                changed = True

            if changed:
                self.site_change_info_list.append(site_info)
                
            # --- 修复并发更新问题：使用 bulk_write 和原子操作 ---
            update_fields = site_info.copy()
            update_fields["update_date"] = curr_date
            
            # 不覆盖 tag，改用 $addToSet 追加 (如果 site_info 带有新 tag)
            new_tags = update_fields.pop("tag", [])
            
            update_op = {"$set": update_fields}
            if new_tags:
                update_op["$addToSet"] = {"tag": {"$each": new_tags}}
                
            bulk_updates.append(UpdateOne({"_id": old_site_info["_id"]}, update_op))

        if bulk_updates:
            try:
                utils.conn_db("asset_site").bulk_write(bulk_updates, ordered=False)
            except Exception as e:
                logger.error("bulk update asset_site error: {}".format(e))

    def build_status_html_report(self):
        html = ""
        style = 'style="border: 0.5pt solid; font-size: 14px;"'

        table_start = '''<table style="border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="border: 0.5pt solid;">编号</th>
                            <th style="border: 0.5pt solid;">站点</th>
                            <th style="border: 0.5pt solid;">变化前状态码</th>
                            <th style="border: 0.5pt solid;">当前状态码</th>
                        </tr>
                    </thead>
                    <tbody>\n'''
        html += table_start

        tr_cnt = 0
        for item in self.status_change_list:
            tr_cnt += 1
            tr_tag = '<tr><td {}> {} </td><td {}> {} </td><td {}>' \
                     '{}</td> <td {}> {} </td></tr>\n'.format(
                style, tr_cnt, style, item["site"], style, item["old_status"], style, item["status"])

            html += tr_tag
            if tr_cnt > 10:
                break

        html += '</tbody></table>'
        return html

    def build_title_html_report(self):
        html = ""
        style = 'style="border: 0.5pt solid; font-size: 14px;"'

        table_start = '''<table style="border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="border: 0.5pt solid;">编号</th>
                            <th style="border: 0.5pt solid;">站点</th>
                            <th style="border: 0.5pt solid;">变化前标题</th>
                            <th style="border: 0.5pt solid;">当前标题</th>
                        </tr>
                    </thead>
                    <tbody>\n'''
        html += table_start

        tr_cnt = 0
        for item in self.title_change_list:
            tr_cnt += 1
            title = item["title"].replace('>', "&#x3e;").replace('<', "&#x3c;")
            old_title = item["old_title"].replace('>', "&#x3e;").replace('<', "&#x3c;")
            tr_tag = '<tr><td {}> {} </td><td {}> {} </td><td {}>' \
                     '{}</td> <td {}> {} </td></tr>\n'.format(
                style, tr_cnt, style, item["site"], style, old_title, style, title)

            html += tr_tag
            if tr_cnt > 10:
                break

        html += '</tbody></table>'
        return html

    def build_length_html_report(self):
        html = ""
        style = 'style="border: 0.5pt solid; font-size: 14px;"'

        table_start = '''<table style="border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="border: 0.5pt solid;">编号</th>
                            <th style="border: 0.5pt solid;">站点</th>
                            <th style="border: 0.5pt solid;">变化前长度</th>
                            <th style="border: 0.5pt solid;">当前长度</th>
                        </tr>
                    </thead>
                    <tbody>\n'''
        html += table_start

        tr_cnt = 0
        for item in self.length_change_list:
            tr_cnt += 1
            tr_tag = '<tr><td {}> {} </td><td {}> {} </td><td {}>' \
                     '{}</td> <td {}> {} </td></tr>\n'.format(
                style, tr_cnt, style, item["site"], style, item["old_length"], style, item["length"])

            html += tr_tag
            if tr_cnt > 10:
                break

        html += '</tbody></table>'
        return html

    def build_html_report(self):
        html = " <br/><br/> 新发现标题变化 {}， 状态码变化 {}， 内容长度变化 {}<br/><br/><br/>".format(
            len(self.title_change_list), len(self.status_change_list), len(self.length_change_list))

        if self.title_change_list:
            title_html = self.build_title_html_report()
            html += title_html

            html += "\n<br/><br/>\n"

        if self.status_change_list:
            status_html = self.build_status_html_report()
            html += status_html
            
            html += "\n<br/><br/>\n"
            
        if self.length_change_list:
            length_html = self.build_length_html_report()
            html += length_html

        return html

    def build_status_markdown_report(self):
        tr_cnt = 0
        markdown = "状态码变化\n\n"

        for item in self.status_change_list:
            tr_cnt += 1
            markdown += "{}. [{}]({})  {} => {} \n".format(tr_cnt,
                                                           item["site"],
                                                           item["site"],
                                                           item["old_status"],
                                                           item["status"]
                                                           )
            if tr_cnt > 5:
                break

        return markdown

    def build_title_markdown_report(self):
        tr_cnt = 0
        markdown = "标题变化\n\n"

        for item in self.title_change_list:
            tr_cnt += 1
            markdown += "{}. [{}]({})  {} => {} \n".format(tr_cnt,
                                                           item["site"],
                                                           item["site"],
                                                           item["old_title"],
                                                           item["title"]
                                                           )
            if tr_cnt > 5:
                break

        return markdown

    def build_length_markdown_report(self):
        tr_cnt = 0
        markdown = "内容实质性变动(Simhash/长度)\n\n"

        for item in self.length_change_list:
            tr_cnt += 1
            distance_str = " (Distance: {})".format(item["distance"]) if item.get("distance", -1) != -1 else ""
            markdown += "{}. [{}]({})  {} => {}{} \n".format(tr_cnt,
                                                           item["site"],
                                                           item["site"],
                                                           item["old_length"],
                                                           item["length"],
                                                           distance_str
                                                           )
            if tr_cnt > 5:
                break

        return markdown

    def build_markdown_report(self):
        markdown = "\n站点监控-{} 灯塔消息推送\n\n".format(self.scope_name)

        markdown += "\n 新发现标题变化 {}， 状态码变化 {}， 内容长度变化 {} \n\n".format(
            len(self.title_change_list), len(self.status_change_list), len(self.length_change_list))

        if self.title_change_list:
            markdown += self.build_title_markdown_report()
            markdown += "\n"

        if self.status_change_list:
            markdown += self.build_status_markdown_report()
            markdown += "\n"
            
        if self.length_change_list:
            markdown += self.build_length_markdown_report()

        return markdown

    def run(self):
        self.build_change_list()
        if not self.status_change_list and not self.title_change_list and not self.length_change_list:
            logger.info("not found change by {}".format(self.scope_id))
            return

        html_title = "[站点监控-{}] 灯塔消息推送".format(self.scope_name)
        markdown_report = self.build_markdown_report()
        from app.utils.push import unified_push
        unified_push("asset_site", html_title, markdown_report)


class Domain2SiteMonitor(object):
    def __init__(self, scope_id):
        self.scope_id = scope_id
        self.site_info_list = []
        self.html_report = ""
        self.dingding_markdown = ""

    def find_not_domain_site(self):
        sites = asset_site.find_site_by_scope_id(self.scope_id)
        domains = asset_domain.find_domain_by_scope_id(self.scope_id)
        ret = []
        if len(domains) == 0:
            return ret

        logger.info("load {} domain, scope_id:{}".format(len(domains), self.scope_id))

        have_domain_site_list = []
        for site in sites:
            netloc = utils.get_hostname(site)
            curr_domain = netloc.split(":")[0]
            have_domain_site_list.append(curr_domain)

        no_domain_site_list = set(domains) - set(have_domain_site_list)
        for domain in no_domain_site_list:
            ret.append("http://{}".format(domain))
            ret.append("https://{}".format(domain))

        logger.info("load {} no_domain_site_list, scope_id:{}".format(len(ret), self.scope_id))

        return ret

    def run(self):
        sites = self.find_not_domain_site()
        if not sites:
            return []

        site_info_list = fetch_site(sites, concurrency=20, http_timeout=(5, 6))

        from urllib.parse import urljoin
        
        # 1. 绝对去重
        dedup_map = {}
        for site_info in site_info_list:
            if site_info["status"] in [502, 504, 501, 422, 410]:
                continue
            if site_info["status"] == 400 and "400" in site_info["title"]:
                continue
            curr_site = site_info["site"]
            if curr_site not in dedup_map:
                dedup_map[curr_site] = site_info
                
        # 2. 交叉对比与智能剪枝
        to_remove = set()
        for curr_site, site_info in dedup_map.items():
            if site_info["status"] in [301, 302, 307, 308]:
                headers = site_info.get("headers", {})
                
                # 检查是否包含有价值的情报（剔除常见无害 Header）
                common_headers = {"server", "date", "content-type", "content-length", "connection", "location", "keep-alive", "x-powered-by"}
                extra = [k for k in headers if k.lower() not in common_headers]
                has_intel = "set-cookie" in [k.lower() for k in headers] or len(extra) > 0
                
                if not has_intel:
                    location = headers.get("Location", headers.get("location", ""))
                    if location:
                        url_3xx = urljoin(curr_site, location)
                        # 场景 A: 如果是同站协议升级 (http -> https) 且 https 已经在列表中，去除旧的
                        if url_3xx.startswith("https://") and curr_site.startswith("http://"):
                            if url_3xx.rstrip('/') == ("https" + curr_site[4:]).rstrip('/') and url_3xx in dedup_map:
                                to_remove.add(curr_site)
                                continue
                        # 场景 B: 目标重定向地址已被收录
                        elif url_3xx in dedup_map and url_3xx != curr_site:
                            to_remove.add(curr_site)
                            continue
                            
        self.site_info_list = [info for url, info in dedup_map.items() if url not in to_remove]

        self.build_report()

        if self.site_info_list:
            self.insert_asset_site()

        return self.site_info_list

    def insert_asset_site(self):
        for site_info in self.site_info_list:
            site_info = site_info.copy()
            site_info["scope_id"] = self.scope_id
            curr_date = utils.curr_date_obj()
            site_info["save_date"] = curr_date
            site_info["update_date"] = curr_date
            raw_tags = site_info.get("tag") or []
            if isinstance(raw_tags, str):
                raw_tags = [raw_tags]
            elif not isinstance(raw_tags, list):
                raw_tags = []
            tags = list(dict.fromkeys(raw_tags))
            if "待测试" not in tags:
                tags.append("待测试")
            site_info["tag"] = tags
            utils.conn_db('asset_site').insert_one(site_info)
        logger.info("save asset_site {} to {}".format(len(self.site_info_list), self.scope_id))

    def build_report(self):
        from app.utils.push import dict2table, dict2dingding_mark
        info_list = []
        tr_cnt = 0
        for site_info in self.site_info_list:
            tr_cnt += 1
            if tr_cnt > 8:
                continue

            info = {
                "站点": site_info['site'],
                "标题": site_info['title'],
                "状态码": site_info['status'],
                "页面长度": site_info['body_length']
            }
            info_list.append(info)

        html = " <br/> 新发现站点 {} <br/>".format(
            len(self.site_info_list))

        html += dict2table(info_list)

        mark = "  新发现站点 {}  ".format(len(self.site_info_list))

        mark += dict2dingding_mark(info_list)

        self.html_report = html
        self.dingding_markdown = mark


def asset_site_monitor(scope_id):
    monitor = AssetSiteMonitor(scope_id=scope_id)
    monitor.run()

