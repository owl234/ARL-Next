from app.services.dns_query import DNSQueryBase
from app import utils


class Query(DNSQueryBase):
    def __init__(self):
        super(Query, self).__init__()
        self.source_name = "anubis"
        self.api_url = "https://jldc.me/anubis/subdomains/"

    def sub_domains(self, target):
        url = f"{self.api_url}{target}"
        try:
            req = utils.http_req(url, 'get', timeout=(15.1, 30.1))
            if req.status_code != 200:
                return []

            data = req.json()
            if not isinstance(data, list):
                return []

            results = []
            for item in data:
                if isinstance(item, str):
                    d = item.strip().lower().replace("*.", "")
                    if d.endswith("." + target) or d == target:
                        results.append(d)

            return list(set(results))
        except Exception as e:
            self.logger.debug(f"anubis query {target} error: {e}")
            return []
