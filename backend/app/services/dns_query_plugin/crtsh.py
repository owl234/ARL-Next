import time
from app.services.dns_query import DNSQueryBase
from app import utils


class Query(DNSQueryBase):
    def __init__(self):
        super(Query, self).__init__()
        self.source_name = "crtsh"
        self.api_url = "https://crt.sh/"

    def sub_domains(self, target):
        param = {
            "output": "json",
            "q": f"%.{target}",
            "exclude": "expired"   # 排除过期的证书
        }

        items = None
        for _ in range(2):
            try:
                req = utils.http_req(self.api_url, 'get', params=param, timeout=(20.1, 40.1))
                if req.status_code == 200:
                    items = req.json()
                    break
            except Exception as e:
                self.logger.debug(f"crt.sh request retry for {target}: {e}")
                time.sleep(1)

        if not items or not isinstance(items, list):
            return []

        results = []
        for item in items:
            name_val = item.get("name_value", "")
            for name in name_val.split():
                name = name.replace("*.", "").strip().lower()
                if name.endswith("." + target) or name == target:
                    results.append(name)

        return list(set(results))


