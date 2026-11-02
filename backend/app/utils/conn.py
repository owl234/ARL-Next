import urllib3
import time
import ssl
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


def create_resilient_ssl_context():
    """
    [第一性原理：极端容错 SSL 上下文]
    针对存在历史包袱的网关设备、过旧或非标嵌入式固件等场景：
    1. 限制最高 TLS 1.2 (规避 TLS 1.3 握手故障或握手不完整)
    2. 设置 SECLEVEL=0 (放宽密钥长度和旧式算法限制)
    3. 启用 OP_IGNORE_UNEXPECTED_EOF (忽略连接过早关闭/不规范 EOF)
    4. 启用 OP_LEGACY_SERVER_CONNECT (允许与旧版不安全服务器重新协商)
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if hasattr(ssl, 'TLSVersion') and hasattr(ssl.TLSVersion, 'TLSv1_2'):
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    elif hasattr(ssl, 'OP_NO_TLSv1_3'):
        ctx.options |= ssl.OP_NO_TLSv1_3

    if hasattr(ssl, 'OP_IGNORE_UNEXPECTED_EOF'):
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF

    legacy_connect = getattr(ssl, 'OP_LEGACY_SERVER_CONNECT', 0x4)
    ctx.options |= legacy_connect

    try:
        ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
    except Exception:
        try:
            ctx.set_ciphers('ALL:@SECLEVEL=0')
        except Exception:
            pass

    return ctx


class ResilientSSLAdapter(requests.adapters.HTTPAdapter):
    """
    容错 SSL 适配器，使用定制的 SSL 上下文
    """
    def __init__(self, *args, **kwargs):
        self.ssl_context = create_resilient_ssl_context()
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)


_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=100)
_scan_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=100)
_resilient_ssl_adapter = ResilientSSLAdapter(pool_connections=200, pool_maxsize=100)

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
    resilient_ssl = kwargs.pop('resilient_ssl', False)

    # Third-party APIs and callbacks carry credentials and must verify TLS.
    # Reconnaissance callers explicitly opt out for self-signed target sites.
    kwargs.setdefault('verify', True)
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
        # Keep insecure target connections out of credential-bearing API pools,
        # including on requests versions predating TLS-aware pool keys.
        if resilient_ssl:
            kwargs['verify'] = False
            session.mount('https://', _resilient_ssl_adapter)
            session.mount('http://', _scan_adapter)
        else:
            adapter = _scan_adapter if kwargs['verify'] is False else _adapter
            session.mount('http://', adapter)
            session.mount('https://', adapter)

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
        if callable(attr) and name in ('insert_one', 'insert_many', 'insert', 'bulk_write'):
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
                except pymongo.errors.BulkWriteError as e:
                    details = getattr(e, 'details', {}) or {}
                    write_errors = details.get('writeErrors', [])
                    duplicate_codes = {11000, 11001, 12582}
                    non_dup_errors = [err for err in write_errors if err.get('code') not in duplicate_codes]
                    concern_errors = details.get('writeConcernErrors', [])

                    if non_dup_errors or concern_errors:
                        logging.getLogger('arlv2').error(
                            f"BulkWriteError on {self._collection.name} with critical errors: "
                            f"non_dup_errors={non_dup_errors}, concern_errors={concern_errors}"
                        )
                    else:
                        logging.getLogger('arlv2').warning(
                            f"Ignored DuplicateKey BulkWriteError on {self._collection.name} ({len(write_errors)} duplicates skipped)"
                        )

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
