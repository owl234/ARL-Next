from bson import ObjectId, json_util
from app import utils
from app.config import Config
from app.helpers.asset_site import build_show_filed_map
import json

logger = utils.get_logger()


class BaseAssetWebHook(object):
    def __init__(self, task_id: str, scope_id: str):
        self.task_id = task_id
        self.scope_id = scope_id
        self.limit_num = 100

    def get_domain_info(self):
        query = {
            "task_id": self.task_id
        }
        fields = ["domain", "record", "type", "ips"]
        show_map = build_show_filed_map(fields)
        items = utils.conn_db('domain').find(query, show_map).limit(self.limit_num)
        return list(items)

    def get_site_info(self):
        query = {
            "task_id": self.task_id
        }
        fields = ["site", "title", "status", "http_server", "body_length"]
        show_map = build_show_filed_map(fields)
        items = utils.conn_db('site').find(query, show_map).limit(self.limit_num)
        return list(items)

    def get_ip_info(self):
        query = {
            "task_id": self.task_id
        }
        fields = ["ip", "port_info", "ip_type", "geo_asn", "geo_city", "cdn_name"]
        show_map = build_show_filed_map(fields)
        items = utils.conn_db('ip').find(query, show_map).limit(self.limit_num)
        return list(items)

    def get_asset_scope_data(self):
        if not self.scope_id or not ObjectId.is_valid(str(self.scope_id)):
            return None
        query = {
            "_id": ObjectId(self.scope_id)
        }
        fields = ["name", "scope_type"]
        show_map = build_show_filed_map(fields)
        item = utils.conn_db('asset_scope').find_one(query, show_map)
        if item:
            item.pop("_id")

        return item

    def get_task_data(self):
        if not self.task_id or not ObjectId.is_valid(str(self.task_id)):
            return None
        query = {
            "_id": ObjectId(self.task_id)
        }
        fields = ["name", "target", "type", "task_tag", "start_time", "status", "end_time", "options"]
        show_map = build_show_filed_map(fields)
        item = utils.conn_db('task').find_one(query, show_map)
        if item:
            item.pop("_id")
        return item


class DomainAssetWebHook(BaseAssetWebHook):
    def __init__(self, task_id: str, scope_id: str, web_hook_url: str, web_hook_token: str):
        super().__init__(task_id, scope_id)
        self.web_hook_url = web_hook_url
        self.web_hook_token = web_hook_token

    def build_data(self):
        data = {
            "type": "domain_monitor",
            "task_id": self.task_id,
            "task_data": self.get_task_data(),
            "scope_id": self.scope_id,
            "scope_data": self.get_asset_scope_data(),
            "asset": {
                "domain_info": self.get_domain_info(),
                "site_info": self.get_site_info(),
            }
        }

        return json.loads(json_util.dumps(data))

    def run_web_hook(self):
        headers = {
            "Token": self.web_hook_token
        }

        data = self.build_data()
        domain_info_list = data["asset"]["domain_info"]
        site_info_list = data["asset"]["site_info"]
        if domain_info_list or site_info_list:
            logger.info("send web_hook to {} domain_info:{}, site_info:{}".format(
                self.web_hook_url, len(domain_info_list), len(site_info_list)))
            utils.http_req(self.web_hook_url,
                           method="post",
                           json=self.build_data(),
                           headers=headers,
                           proxy_domain="intel")


class IPAssetWebHook(BaseAssetWebHook):
    def __init__(self, task_id: str, scope_id: str, web_hook_url: str, web_hook_token: str):
        super().__init__(task_id, scope_id)
        self.web_hook_url = web_hook_url
        self.web_hook_token = web_hook_token

    def build_data(self):
        data = {
            "type": "ip_monitor",
            "task_id": self.task_id,
            "task_data": self.get_task_data(),
            "scope_id": self.scope_id,
            "scope_data": self.get_asset_scope_data(),
            "asset": {
                "ip_info": self.get_ip_info(),
                "site_info": self.get_site_info(),
            }
        }

        return json.loads(json_util.dumps(data))

    def run_web_hook(self):
        headers = {
            "Token": self.web_hook_token
        }

        data = self.build_data()
        ip_info_list = data["asset"]["ip_info"]
        site_info_list = data["asset"]["site_info"]
        if ip_info_list or site_info_list:
            logger.info("send web_hook to {} ip_info:{}, site_info:{}".format(
                self.web_hook_url, len(ip_info_list), len(site_info_list)))
            utils.http_req(self.web_hook_url,
                           method="post",
                           json=self.build_data(),
                           headers=headers,
                           proxy_domain="intel")


class SiteAssetWebHook(BaseAssetWebHook):
    def __init__(self, task_id: str, scope_id: str, web_hook_url: str, web_hook_token: str):
        super().__init__(task_id, scope_id)
        self.web_hook_url = web_hook_url
        self.web_hook_token = web_hook_token

    def build_data(self):
        data = {
            "type": "site_monitor",
            "task_id": self.task_id,
            "task_data": self.get_task_data(),
            "scope_id": self.scope_id,
            "scope_data": self.get_asset_scope_data(),
            "asset": {
                "site_info": self.get_site_info(),
            }
        }

        return json.loads(json_util.dumps(data))

    def run_web_hook(self):
        headers = {
            "Token": self.web_hook_token
        }

        data = self.build_data()
        site_info_list = data["asset"]["site_info"]
        if site_info_list:
            logger.info("send web_hook to {} site_info:{}".format(
                self.web_hook_url, len(site_info_list)))
            utils.http_req(self.web_hook_url,
                           method="post",
                           json=self.build_data(),
                           headers=headers,
                           proxy_domain="intel")


def domain_asset_web_hook(task_id: str, scope_id: str):
    try:
        url = Config.WEB_HOOK_URL
        token = Config.WEB_HOOK_TOKEN
        if url:
            d = DomainAssetWebHook(task_id=task_id, scope_id=scope_id,
                                   web_hook_url=url, web_hook_token=token)
            d.run_web_hook()
    except Exception as e:
        logger.error(str(e))


def ip_asset_web_hook(task_id: str, scope_id: str):
    try:
        url = Config.WEB_HOOK_URL
        token = Config.WEB_HOOK_TOKEN
        if url:
            d = IPAssetWebHook(task_id=task_id, scope_id=scope_id,
                               web_hook_url=url, web_hook_token=token)
            d.run_web_hook()
    except Exception as e:
        logger.error(str(e))


class NucleiVulnWebHook(BaseAssetWebHook):
    _RESULT_FIELDS = (
        "template_id", "vuln_name", "vuln_severity", "vuln_url",
        "target", "host", "template_url", "extracted_results",
        "curl_command", "save_date",
    )

    def __init__(self, task_id: str, scope_id: str, web_hook_url: str, web_hook_token: str,
                 nuclei_results: list = None, task_data: dict = None):
        super().__init__(task_id, scope_id)
        self.web_hook_url = web_hook_url
        self.web_hook_token = web_hook_token
        self.nuclei_results = nuclei_results or []
        self._task_data = task_data

    def _serialize_task_data(self):
        raw = self.get_task_data() or self._task_data
        if not isinstance(raw, dict):
            return None
        allowed = ("name", "target", "type", "task_tag", "start_time", "status", "end_time", "options")
        return {k: raw.get(k) for k in allowed if k in raw}

    def _serialize_results(self):
        serialized = []
        for item in self.nuclei_results[:self.limit_num]:
            if not isinstance(item, dict):
                continue
            serialized.append({k: item.get(k) for k in self._RESULT_FIELDS if k in item})
        return serialized

    def build_data(self):
        from app.utils.push import count_nuclei_severities
        severity_counts = count_nuclei_severities(self.nuclei_results)
        data = {
            "type": "nuclei_vuln",
            "task_id": self.task_id,
            "task_data": self._serialize_task_data(),
            "scope_id": self.scope_id or "",
            "scope_data": self.get_asset_scope_data(),
            "summary": {
                "total": len(self.nuclei_results),
                "truncated": len(self.nuclei_results) > self.limit_num,
                "severity_counts": severity_counts,
            },
            "nuclei_results": self._serialize_results(),
        }
        return json.loads(json_util.dumps(data))

    def run_web_hook(self):
        if not self.nuclei_results:
            return
        headers = {}
        if self.web_hook_token:
            headers["Token"] = self.web_hook_token
        data = self.build_data()
        logger.info("send nuclei_vuln web_hook to {} count:{}".format(
            self.web_hook_url, len(self.nuclei_results)))
        conn = utils.http_req(
            self.web_hook_url,
            method="post",
            json=data,
            headers=headers,
            timeout=10,
            proxy_domain="intel",
        )
        if getattr(conn, "status_code", 200) >= 400:
            logger.warning("nuclei_vuln web_hook response error: status={}".format(conn.status_code))


def site_asset_web_hook(task_id: str, scope_id: str):
    try:
        url = Config.WEB_HOOK_URL
        token = Config.WEB_HOOK_TOKEN
        if url:
            d = SiteAssetWebHook(task_id=task_id, scope_id=scope_id,
                                 web_hook_url=url, web_hook_token=token)
            d.run_web_hook()
    except Exception as e:
        logger.error(str(e))


def nuclei_vuln_web_hook(task_id: str, scope_id: str = "", nuclei_results: list = None, task_data: dict = None):
    try:
        url = Config.WEB_HOOK_URL
        token = Config.WEB_HOOK_TOKEN
        if url and nuclei_results:
            d = NucleiVulnWebHook(
                task_id=task_id,
                scope_id=scope_id or "",
                web_hook_url=url,
                web_hook_token=token,
                nuclei_results=nuclei_results,
                task_data=task_data,
            )
            d.run_web_hook()
    except Exception as e:
        logger.error(f"nuclei_vuln_web_hook error: {e}")
