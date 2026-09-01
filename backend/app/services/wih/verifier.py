# -*- coding: utf-8 -*-
"""
Pluggable Cloud Credential & Token Live Verifiers.
Supports Alibaba Cloud, Tencent Cloud, JD Cloud, and JWT token analysis.
All verifiers are optional and strictly non-intrusive by default.
"""

import json
import base64
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("arlv2.wih")


def parse_jwt_payload(jwt_token: str) -> Optional[Dict[str, Any]]:
    """
    Parse and decode JWT token payload without remote requests.
    """
    if not jwt_token:
        return None
    try:
        parts = jwt_token.strip().split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            # Add padding
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            decoded = base64.urlsafe_b64decode(payload_b64)
            return json.loads(decoded)
    except Exception as e:
        logger.debug(f"Error decoding JWT payload: {e}")
    return None


def verify_alicloud_ak(ak: str, sk: Optional[str] = None) -> Dict[str, Any]:
    """
    Optional check for Alibaba Cloud AccessKey (requires explicit user intent).
    """
    result = {"valid": False, "provider": "alicloud", "ak": ak}
    if not ak or not ak.startswith("LTAI"):
        return result
    # Passive format validation
    if len(ak) >= 16 and len(ak) <= 30:
        result["format_valid"] = True
    return result


def verify_tencentcloud_ak(ak: str, sk: Optional[str] = None) -> Dict[str, Any]:
    """
    Optional check for Tencent Cloud AccessKey.
    """
    result = {"valid": False, "provider": "tencentcloud", "ak": ak}
    if not ak or not ak.startswith("AKID"):
        return result
    if len(ak) >= 17 and len(ak) <= 40:
        result["format_valid"] = True
    return result
