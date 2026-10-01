# backend/app/adapters/vuln_platform/dedup.py
"""基于 SHA-256 内容指纹的增量去重器"""

import hashlib
from urllib.parse import urlparse

from app import utils

logger = utils.get_logger()


class IncrementalDeduplicator(object):

    @staticmethod
    def normalize_domain(domain):
        domain = domain.strip().lower()
        if "://" in domain:
            domain = urlparse(domain).netloc
        return domain.split(":")[0]

    @classmethod
    def compute_subdomain_fingerprint(cls, subdomain):
        return hashlib.sha256(
            cls.normalize_domain(subdomain).encode()).hexdigest()

    @classmethod
    def compute_scope_fingerprint(cls, scope_list):
        normalized = sorted(
            set(cls.normalize_domain(s) for s in scope_list))
        return hashlib.sha256("|".join(normalized).encode()).hexdigest()

    @classmethod
    def compute_project_fingerprint(cls, platform, project_id,
                                     scope_fingerprint):
        content = "{}:{}:{}".format(
            platform, project_id, scope_fingerprint)
        return hashlib.sha256(content.encode()).hexdigest()