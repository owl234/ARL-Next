from urllib.parse import urlparse
from app.services.dns_query import DNSQueryBase
from app import utils


class Query(DNSQueryBase):
    def __init__(self):
        super(Query, self).__init__()
        self.source_name = "wayback"
        self.api_url = "http://web.archive.org/cdx/search/cdx"

    def sub_domains(self, target):
        param = {
            "url": f"*.{target}/*",
            "output": "json",
            "collapse": "urlkey",
            "fl": "original",
            "limit": "5000"
        }
        try:
            req = utils.http_req(self.api_url, 'get', params=param, timeout=(20.1, 40.1))
            if req.status_code != 200:
                return []

            data = req.json()
            if not isinstance(data, list) or len(data) <= 1:
                return []

            results = []
            for item in data[1:]:  # skip header row
                if isinstance(item, list) and item:
                    u = item[0]
                elif isinstance(item, str):
                    u = item
                else:
                    continue

                if not u.startswith("http"):
                    u = "http://" + u

                host = urlparse(u).hostname
                if host:
                    host = host.strip().lower().replace("*.", "")
                    if host.endswith("." + target) or host == target:
                        results.append(host)

            return list(set(results))
        except Exception as e:
            self.logger.debug(f"wayback query {target} error: {e}")
            return []
