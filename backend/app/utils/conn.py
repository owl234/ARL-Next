import urllib3
import time
import requests
from app.config import Config
from pymongo import MongoClient
import pymongo.errors
import logging
from requests.exceptions import ReadTimeout

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


CONTENT_CHUNK_SIZE = 10 * 1024


UA = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"


proxies = {
    'https': "http://127.0.0.1:8080",
    'http': "http://127.0.0.1:8080"
}

SET_PROXY = False


_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=100)

class StatelessSession(requests.Session):
    def close(self):
        pass
# requests/models.py:824
def patch_content(response, timeout=None, max_size=10*1024*1024):
    """Content of the response, in bytes."""
    start_at = time.time()
    if response._content is False:
        # Read the contents.
        if response._content_consumed:
            raise RuntimeError("The content for this response was already consumed")

        if response.status_code == 0 or response.raw is None:
            response._content = None
        else:
            body = b''
            for part in response.iter_content(CONTENT_CHUNK_SIZE):
                body += part
                if timeout is not None and time.time() - start_at >= timeout:
                    raise ReadTimeout(f"patch_content read http response timeout: {timeout}")
                if len(body) >= max_size:
                    response.raw.close()
                    break
            response._content = body
    response._content_consumed = True
    # don't need to release the connection; that's been handled by urllib3
    # since we exhausted the data.
    return response._content


def http_req(url, method='get', **kwargs):
    kwargs.setdefault('verify', False)
    kwargs.setdefault('timeout', (10.1, 30.1))
    kwargs.setdefault('allow_redirects', False)

    headers = kwargs.get("headers", {})
    headers.setdefault("User-Agent", UA)
    # 不允许缓存
    headers.setdefault("Cache-Control", "max-age=0")

    kwargs["headers"] = headers
    kwargs["stream"] = True

    if Config.PROXY_URL:
        proxies['https'] = Config.PROXY_URL
        proxies['http'] = Config.PROXY_URL
        kwargs["proxies"] = proxies

    with StatelessSession() as session:
        # 必须清空自带的默认 Adapter 避免未关闭造成潜在的内存泄漏
        session.adapters.clear()
        session.mount('http://', _adapter)
        session.mount('https://', _adapter)
        conn = getattr(session, method)(url, **kwargs)

        timeout = kwargs.get("timeout")
        try:
            if isinstance(timeout, (list, tuple)) and len(timeout) > 1 and timeout[1]:
                timeout = timeout[1]
        except Exception:
            pass

        try:
            patch_content(conn, timeout)
        except Exception:
            conn.close()
            raise

    return conn


class ConnMongo(object):
    def __new__(cls):
        import os
        pid = os.getpid()
        if not hasattr(cls, 'instance') or getattr(cls, '_pid', None) != pid:
            cls.instance = super(ConnMongo, cls).__new__(cls)
            cls.instance.conn = MongoClient(Config.MONGO_URL, connect=False)
            cls._pid = pid
        return cls.instance


class SafeCollectionProxy:
    def __init__(self, collection):
        self._collection = collection

    def __getattr__(self, name):
        attr = getattr(self._collection, name)
        if callable(attr) and name in ('insert_one', 'insert_many', 'insert'):
            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except pymongo.errors.DuplicateKeyError as e:
                    logging.getLogger('arlv2').warning(f"Ignored DuplicateKeyError on {self._collection.name}: {e}")
                    class DummyResult:
                        inserted_id = None
                        inserted_ids = []
                        acknowledged = False
                    return DummyResult()
            return wrapper
        return attr

def conn_db(collection, db_name = None):

    conn = ConnMongo().conn
    if db_name:
        return SafeCollectionProxy(conn[db_name][collection])

    else:
        return SafeCollectionProxy(conn[Config.MONGO_DB][collection])