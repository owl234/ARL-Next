import threading
from app.helpers import asset_site, asset_domain
from app import utils
from app.helpers.scope import get_scope_by_scope_id
from app.helpers.message_notify import push_email, push_dingding
from app.helpers.asset_site_monitor import is_black_asset_site
from .baseThread import BaseThread
from .fetchSite import fetch_site


logger = utils.get_logger()


class AssetSiteCompare(BaseThread):
    def __init__(self, scope_id):
        self._scope_id = scope_id
        sites = asset_site.find_site_by_scope_id(scope_id)
        logger.info("load {}  site from {}".format(len(sites), self._scope_id))
        super(AssetSiteCompare, self).__init__(targets=sites, concurrency=15)
        self.new_site_info_map = {}
        self.mutex = threading.Lock()
        self.site_change_map = {}

    def work(self, site):
        if is_black_asset_site(site):
            logger.debug("{} in black asset site".format(site))
            return

        conn = utils.http_req(site)
        item = {
            "title": utils.get_title(conn.content),
            "status": conn.status_code,
            "body_length": len(conn.content)
        }
        with self.mutex:
            self.new_site_info_map[site] = item

    def compare(self):
        site_info_list = asset_site.find_site_info_by_scope_id(scope_id=self._scope_id)
        for site_info in site_info_list:
            curr_site = site_info["site"]
            # 访问不了的站点和黑名单站点，跳过
            if curr_site not in self.new_site_info_map:
                continue

            new_site_info = self.new_site_info_map[curr_site]

            old_title = site_info.get("title", "")
            old_status = site_info.get("status", 0)
            old_length = site_info.get("body_length", 0)

            if new_site_info["title"] != old_title:
                # 只关注标题不为空
                if new_site_info["title"]:
                    self.site_change_map[curr_site] = site_info

            if new_site_info["status"] != old_status:
                self.site_change_map[curr_site] = site_info

            if old_length > 0:
                length_diff = abs(new_site_info.get("body_length", 0) - old_length)
                if length_diff / old_length > 0.05:
                    self.site_change_map[curr_site] = site_info
            elif new_site_info.get("body_length", 0) > 0:
                utils.conn_db("asset_site").update_one(
                    {"_id": site_info["_id"]},
                    {"$set": {"body_length": new_site_info["body_length"]}}
                )

    def run(self):
        self._run()
        self.compare()

        # 已经用完了省一点空间。
        self.new_site_info_map.clear()

        return self.site_change_map


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

    def compare_length(self, site_info, old_site_info):
        curr_length = site_info.get("body_length", 0)
        old_length = old_site_info.get("body_length", 0)
        curr_site = site_info["site"]

        if old_length > 0 and curr_length > 0:
            diff = abs(curr_length - old_length)
            if diff / old_length > 0.05:
                item = {
                    "site": curr_site,
                    "length": curr_length,
                    "old_length": old_length
                }
                logger.info("{} length {} => {}".format(curr_site, old_length, curr_length))
                self.length_change_list.append(item)
                return True
        return False

    def build_change_list(self):
        compare = AssetSiteCompare(scope_id=self.scope_id)
        # 根据资产组中的站点去重新请求，并比对状态码和标题。
        site_change_map = compare.run()
        sites = list(site_change_map.keys())

        if not sites:
            logger.info("not found change ok site, scope_id: {}".format(self.scope_id))
            return

        logger.info("found scope site {}, scope_id: {}".format(len(sites), self.scope_id))

        site_info_list = fetch_site(sites)

        for site_info in site_info_list:
            curr_site = site_info["site"]
            if curr_site not in site_change_map:
                continue

            old_site_info = site_change_map[curr_site]
            
            is_entry = "入口" in site_info.get("tag", [])
            was_entry = "入口" in old_site_info.get("tag", [])

            # --- 防抖逻辑 (Plan 1 + Plan 3: 基于状态机的延迟确认与分级容错) ---
            curr_status = site_info.get("status", 0)
            if curr_status >= 400:
                # 核心资产容忍 2 次周期连续失败，边缘资产容忍 3 次周期
                tolerance_limit = 2 if (is_entry or was_entry) else 3
                current_count = old_site_info.get("consecutive_error_count", 0) + 1
                site_info["consecutive_error_count"] = current_count
                
                # 若未达到硬状态阈值，拦截告警并挂起状态更新，仅刷新计数器
                if current_count < tolerance_limit:
                    utils.conn_db("asset_site").update_one(
                        {"_id": old_site_info["_id"]},
                        {"$set": {"consecutive_error_count": current_count}}
                    )
                    continue
            else:
                site_info["consecutive_error_count"] = 0
            # -------------------------------------------------------------

            # 若新老数据都被判断为非入口，且不再是关键状态变更，则只静默同步数据库，不发告警
            if not is_entry and not was_entry:
                self.update_asset_site(old_site_info["_id"], site_info)
                continue

            changed = False
            if self.compare_title(site_info, old_site_info):
                changed = True

            if self.compare_status(site_info, old_site_info):
                changed = True

            if self.compare_length(site_info, old_site_info):
                changed = True

            if changed:
                self.site_change_info_list.append(site_info)
                
            # 无论是否触发告警记录，都保证底层数据库能够跟现实世界状态对齐
            self.update_asset_site(old_site_info["_id"], site_info)

    # 更新资产分组站点信息（修复：保留原有 _id、task_id 及截图等元数据，避免外键和文件引用断裂）
    def update_asset_site(self, asset_id, site_info):
        query = {
            "_id": asset_id
        }
        copy_site_info = site_info.copy()
        copy_site_info["update_date"] = utils.curr_date_obj()

        # 读写 Merge 机制：合并原有的 tag，防止覆写人工标签
        current_record = utils.conn_db("asset_site").find_one(query)
        if current_record and "tag" in current_record:
            old_tags = set(current_record.get("tag", []))
            new_tags = set(copy_site_info.get("tag", []))
            copy_site_info["tag"] = list(old_tags | new_tags)

        utils.conn_db("asset_site").update_one(query, {"$set": copy_site_info})

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
        markdown = "正文长度变化(>5%)\n\n"

        for item in self.length_change_list:
            tr_cnt += 1
            markdown += "{}. [{}]({})  {} => {} \n".format(tr_cnt,
                                                           item["site"],
                                                           item["site"],
                                                           item["old_length"],
                                                           item["length"]
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

        # 过滤 502, 504
        for site_info in site_info_list:
            if site_info["status"] in [502, 504, 501, 422, 410]:
                continue

            # 过滤400 状态码
            if site_info["status"] == 400 and "400" in site_info["title"]:
                continue

            self.site_info_list.append(site_info)

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

