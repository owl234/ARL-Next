from app.services.dns_query import DNSQueryBase
from app import utils


class Query(DNSQueryBase):
    def __init__(self):
        super(Query, self).__init__()
        self.source_name = "hackertarget"
        self.api_url = "https://api.hackertarget.com/hostsearch/"

    def sub_domains(self, target):
        param = {
            "q": target
        }
        try:
            req = utils.http_req(self.api_url, 'get', params=param, timeout=(15.1, 25.1))
            if req.status_code != 200:
                return []

            content = req.text
            if not content or "error check your search parameter" in content or "API count exceeded" in content:
                return []

            results = []
            for line in content.splitlines():
                parts = line.strip().split(",")
                if parts:
                    domain = parts[0].strip().lower()
                    if domain.endswith("." + target) or domain == target:
                        results.append(domain)

            return list(set(results))
        except Exception as e:
            self.logger.warning(f"hackertarget query {target} error: {e}")
            return []
