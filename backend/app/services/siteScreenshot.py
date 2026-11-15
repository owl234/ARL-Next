import os
import re
import time
import base64
import requests
from app import utils
from .baseThread import BaseThread
logger = utils.get_logger()

PUPPETEER_URL = os.environ.get("PUPPETEER_URL", "http://arl-puppeteer:5005")


def _get_puppeteer_proxy(site):
    try:
        from app.services.proxy_service import resolve_puppeteer_proxy
        proxy_url, _ = resolve_puppeteer_proxy(target_url=site)
        return proxy_url or ""
    except Exception:
        return ""


class SiteScreenshot(BaseThread):
    def __init__(self, sites, concurrency=3, capture_dir="./"):
        super().__init__(sites, concurrency=concurrency)
        self.capture_dir = capture_dir
        self.screenshot_map = {}
        os.makedirs(self.capture_dir, 0o777, True)

    def gen_filename(self, site):
        filename = site.replace('://', '_')
        return re.sub(r'[^\w\-_\. ]', '_', filename)
        
    def work(self, site):
        file_name = '{}/{}.jpg'.format(self.capture_dir, self.gen_filename(site))
        self.screenshot_map[site] = file_name
        
        logger.debug("SiteScreenshot HTTP => {}".format(site))
        max_retries = 3
        proxy_server = _get_puppeteer_proxy(site)
        for attempt in range(max_retries):
            try:
                payload = {"url": site}
                if proxy_server:
                    payload["proxy_server"] = proxy_server
                res = requests.post(f"{PUPPETEER_URL}/screenshot", json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("base64"):
                        img_data = base64.b64decode(data["base64"])
                        with open(file_name, "wb") as f:
                            f.write(img_data)
                    return
                elif res.status_code == 503:
                    if attempt == 0:
                        logger.warning("SiteScreenshot HTTP 503 for {}, arl-puppeteer is busy/restarting. Retrying in 2s...".format(site))
                        time.sleep(2)
                        continue
                    else:
                        logger.warning("SiteScreenshot HTTP 503 for {} again. Stop retrying to save time.".format(site))
                        return
                else:
                    logger.warning("SiteScreenshot HTTP Error {} for {}".format(res.status_code, site))
                    return
            except requests.exceptions.ConnectionError:
                if attempt == 0:
                    logger.warning("SiteScreenshot ConnectionError for {}. Retrying in 2s...".format(site))
                    time.sleep(2)
                    continue
                else:
                    logger.warning("SiteScreenshot ConnectionError for {} again. Stop retrying.".format(site))
                    return
            except Exception as e:
                logger.warning("SiteScreenshot failed for {}: {}".format(site, e))
                return
        
        logger.error("SiteScreenshot failed for {} after {} retries.".format(site, max_retries))

    def run(self):
        t1 = time.time()
        logger.info("start screen shot batch, total: {}".format(len(self.targets)))
        if not self.targets:
            return
            
        self._run()

        elapse = time.time() - t1
        logger.info("end screen shot batch elapse {:.2f}s".format(elapse))

def site_screenshot(sites, concurrency=3, capture_dir="./"):
    s = SiteScreenshot(sites, concurrency=concurrency, capture_dir=capture_dir)
    s.run()