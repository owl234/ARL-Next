# -*- coding: utf-8 -*-
"""
WIH Rule Engine & Sensitive Pattern Matcher.
Loads YAML rules from , pre-compiles regex patterns,
and applies safe multi-tier extraction with exclude rules filtering.
Includes zero-dependency fallback parser when PyYAML is unavailable.
"""

import os
import re
import logging
from typing import List, Dict, Tuple, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger("arlv2.wih")

def _get_default_rule_path():
    try:
        from app.config import Config
        if hasattr(Config, "WIH_RULE_PATH") and os.path.exists(Config.WIH_RULE_PATH):
            return Config.WIH_RULE_PATH
    except Exception:
        pass
    basedir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(basedir, "dicts", "wih_rules.yml")

# Common non-target false positive domains in third-party JS
DEFAULT_IGNORED_DOMAINS = {
    "w3.org", "www.w3.org", "schema.org", "github.com", "google.com",
    "googleapis.com", "gstatic.com", "baidu.com", "qq.com", "taobao.com",
    "alipay.com", "jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
    "ampproject.org", "apache.org", "mozilla.org", "facebook.com", "twitter.com",
    "google-analytics.com", "googletagmanager.com", "sentry.io", "doubleclick.net",
    "cloudflare.com", "fastly.net", "bootcss.com", "staticfile.org"
}

IGNORED_DOMAIN_EXTS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".map", ".json", ".xml",
    ".html", ".htm", ".mp4", ".mp3", ".webm", ".wasm", ".zip", ".tar", ".gz"
}

BUILTIN_DOMAIN_PATTERN = re.compile(
    r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+'
    r'(?:com|cn|org|net|edu|gov|io|co|cc|me|top|xyz|vip|ltd|site|tech|online|store|pro|club|fun|link|app|dev|cloud|ai|so|tv|la|us|uk|hk|tw|jp|de|fr|info|biz|icu|xin|wang|ren|pub|mobi|asia)\b',
    re.IGNORECASE
)

BUILTIN_SECRET_KEY_PATTERN = re.compile(
    r'(?i)(?:secret_?key|app_?secret|access_?secret|api_?secret|secret_?token|client_?secret|app_?key|private_?key)'
    r'\s*[:=]\s*[\'\"]([a-zA-Z0-9_\-]{20,80})[\'\"]'
)


class ExcludeRuleMatcher:
    def __init__(self, rule_dict: dict):
        self.name = rule_dict.get("name", "")
        self.enabled = rule_dict.get("enabled", True)
        self.rule_id = rule_dict.get("id")
        
        self.target_pattern = self._compile_match_pattern(rule_dict.get("target"))
        self.content_pattern = self._compile_match_pattern(rule_dict.get("content"))
        self.source_pattern = self._compile_match_pattern(rule_dict.get("source"))
        self.source_tag = rule_dict.get("source_tag")

    def _compile_match_pattern(self, val: Optional[str]):
        if not val:
            return None
        if isinstance(val, str) and val.startswith("regex:"):
            raw_regex = val[len("regex:"):]
            try:
                return re.compile(raw_regex, re.IGNORECASE)
            except Exception as e:
                logger.warning(f"Invalid exclude rule regex {val}: {e}")
                return None
        return val

    def matches(self, record_type: str, content: str, target_site: str, source_url: str, source_tag: str = "") -> bool:
        if not self.enabled:
            return False

        if self.rule_id and self.rule_id != record_type:
            return False

        if self.target_pattern:
            if isinstance(self.target_pattern, re.Pattern):
                if not self.target_pattern.search(target_site):
                    return False
            elif isinstance(self.target_pattern, str):
                if self.target_pattern not in target_site:
                    return False

        if self.content_pattern:
            if isinstance(self.content_pattern, re.Pattern):
                if not self.content_pattern.search(content):
                    return False
            elif isinstance(self.content_pattern, str):
                if self.content_pattern not in content:
                    return False

        if self.source_pattern:
            if isinstance(self.source_pattern, re.Pattern):
                if not self.source_pattern.search(source_url):
                    return False
            elif isinstance(self.source_pattern, str):
                if self.source_pattern not in source_url:
                    return False

        if self.source_tag and self.source_tag != source_tag:
            return False

        return True


class WihRuleEngine:
    """
    Thread-safe, pre-compiled WIH rule engine.
    """
    def __init__(self, rule_yaml_path: Optional[str] = None):
        self.rule_path = rule_yaml_path or _get_default_rule_path()
        self.rules: List[Dict[str, Any]] = []
        self.exclude_rules: List[ExcludeRuleMatcher] = []
        self.load_rules()

    def _parse_yaml_fallback(self, content: str) -> dict:
        """
        Zero-dependency lightweight parser for standard wih_rules.yml structure.
        """
        result = {"rules": [], "exclude_rules": []}
        current_section = None
        current_item = {}

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if line_str.startswith("rules:"):
                current_section = "rules"
                continue
            elif line_str.startswith("exclude_rules:"):
                if current_item and current_section:
                    result[current_section].append(current_item)
                    current_item = {}
                current_section = "exclude_rules"
                continue

            if line_str.startswith("-"):
                if current_item and current_section:
                    result[current_section].append(current_item)
                current_item = {}
                line_str = line_str[1:].strip()

            if ":" in line_str:
                parts = line_str.split(":", 1)
                k = parts[0].strip()
                val_raw = parts[1].strip()

                if val_raw.startswith('"'):
                    end_q = val_raw.rfind('"')
                    if end_q > 0:
                        val_raw = val_raw[1:end_q]
                elif val_raw.startswith("'"):
                    end_q = val_raw.rfind("'")
                    if end_q > 0:
                        val_raw = val_raw[1:end_q]
                else:
                    if "#" in val_raw:
                        val_raw = val_raw.split("#", 1)[0].strip()
                    val_raw = val_raw.strip('\'"')

                v = val_raw
                if isinstance(v, str):
                    if v.lower() == "true":
                        v = True
                    elif v.lower() == "false":
                        v = False
                current_item[k] = v

        if current_item and current_section:
            result[current_section].append(current_item)

        return result

    def load_rules(self):
        self.rules.clear()
        self.exclude_rules.clear()

        if not os.path.exists(self.rule_path):
            logger.warning(f"WIH rule path not found: {self.rule_path}, using built-in defaults")
            self._load_default_fallback_rules()
            return

        try:
            with open(self.rule_path, "r", encoding="utf-8") as f:
                content = f.read()

            if yaml is not None:
                data = yaml.safe_load(content) or {}
            else:
                data = self._parse_yaml_fallback(content)

            raw_rules = data.get("rules", [])
            for r in raw_rules:
                if not r.get("enabled", False):
                    continue
                rule_id = r.get("id", "")
                pattern_str = r.get("pattern", "")
                
                compiled = None
                if pattern_str:
                    try:
                        compiled = re.compile(pattern_str)
                    except Exception as e:
                        logger.warning(f"Error compiling WIH rule [{rule_id}]: {e}")
                        continue
                
                self.rules.append({
                    "id": rule_id,
                    "compiled": compiled,
                    "raw_pattern": pattern_str
                })

            raw_exclude = data.get("exclude_rules", [])
            for ex in raw_exclude:
                if ex.get("enabled", True):
                    self.exclude_rules.append(ExcludeRuleMatcher(ex))

            logger.info(f"Loaded {len(self.rules)} active WIH rules and {len(self.exclude_rules)} exclude rules")
        except Exception as e:
            logger.error(f"Failed to load WIH rule YAML {self.rule_path}: {e}")
            self._load_default_fallback_rules()

    def _load_default_fallback_rules(self):
        self.rules.append({"id": "domain", "compiled": None})
        self.rules.append({"id": "secret_key", "compiled": None})
        self.rules.append({"id": "Aliyun_AK_ID", "compiled": re.compile(r"\bLTAI[A-Za-z\d]{12,30}\b")})
        self.rules.append({"id": "QCloud_AK_ID", "compiled": re.compile(r"\bAKID[A-Za-z\d]{13,40}\b")})
        self.rules.append({"id": "jwt_token", "compiled": re.compile(r"eyJ[A-Za-z0-9_\-+/]{10,}={0,2}\.[A-Za-z0-9_\-+/]{15,}={0,2}\.[A-Za-z0-9_\-+/]{10,}={0,2}")})

    def is_excluded(self, record_type: str, content: str, target_site: str, source_url: str, source_tag: str = "") -> bool:
        for ex in self.exclude_rules:
            if ex.matches(record_type, content, target_site, source_url, source_tag):
                return True
        return False

    def extract_from_text(self, text: str, target_site: str = "", source_url: str = "", source_tag: str = "") -> List[Tuple[str, str]]:
        if not text:
            return []

        results: List[Tuple[str, str]] = []
        seen_matches = set()

        for rule in self.rules:
            rule_id = rule["id"]
            compiled_re = rule.get("compiled")

            # 1. Built-in Domain Extraction
            if rule_id == "domain":
                for match in BUILTIN_DOMAIN_PATTERN.finditer(text):
                    d = match.group(0)
                    d_clean = d.strip(".").lower()
                    if d_clean.startswith("eyj") or any(d_clean.endswith(ext) for ext in IGNORED_DOMAIN_EXTS):
                        continue
                    if d_clean in DEFAULT_IGNORED_DOMAINS:
                        continue
                    if len(d_clean) < 4 or d_clean.count(".") == 0 or any(len(part) > 63 for part in d_clean.split(".")):
                        continue
                    
                    key = (rule_id, d_clean)
                    if key not in seen_matches:
                        if not self.is_excluded(rule_id, d_clean, target_site, source_url, source_tag):
                            seen_matches.add(key)
                            results.append(key)

            # 2. Built-in SecretKey Extraction
            elif rule_id == "secret_key":
                for match in BUILTIN_SECRET_KEY_PATTERN.finditer(text):
                    m_clean = match.group(1).strip() if match.lastindex else match.group(0).strip()
                    if len(m_clean) >= 16:
                        key = (rule_id, m_clean)
                        if key not in seen_matches:
                            if not self.is_excluded(rule_id, m_clean, target_site, source_url, source_tag):
                                seen_matches.add(key)
                                results.append(key)

            # 3. Custom Regex Rule
            elif compiled_re:
                for match in compiled_re.finditer(text):
                    if match.lastindex and match.lastindex >= 1:
                        m_clean = match.group(1).strip()
                    else:
                        m_clean = match.group(0).strip()
                    
                    if not m_clean:
                        continue
                    
                    if rule_id in ("wechat_appid", "wechat_corpid", "wechat_id", "AWS_AK_ID"):
                        m_clean = m_clean.strip('\'" ')

                    key = (rule_id, m_clean)
                    if key not in seen_matches:
                        if not self.is_excluded(rule_id, m_clean, target_site, source_url, source_tag):
                            seen_matches.add(key)
                            results.append(key)

        return results
