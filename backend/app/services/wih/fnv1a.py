# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Union

"""
64-bit FNV-1a Hash Implementation.
Strictly bit-aligned with Go language standard library `hash/fnv` (fnv.New64a()).
"""

FNV_OFFSET_64 = 14695981039346656037  # 0xcbf29ce484222325
FNV_PRIME_64 = 1099511628211          # 0x100000001b3
MASK_64 = 0xFFFFFFFFFFFFFFFF          # 2^64 - 1


def fnv1a_64(data: bytes | str) -> str:
    """
    Calculate standard 64-bit FNV-1a hash.
    
    ⚠️ Performance Note: 纯 Python 字节级迭代，设计用于对匹配到的敏感内容（通常几十~几百字符）
    计算去重哈希，而非对整个 JS 文件全文计算。请勿对 MB 级大文本调用此函数。
    
    :param data: String or UTF-8 encoded bytes
    :return: String representation of 64-bit unsigned integer (e.g. "8618312879776256743")
    """
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")

    h = FNV_OFFSET_64
    for b in data:
        h = ((h ^ b) * FNV_PRIME_64) & MASK_64

    return str(h)


def fnv1a_64_int(data: bytes | str) -> int:
    """
    Calculate standard 64-bit FNV-1a hash returning integer.
    """
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")

    h = FNV_OFFSET_64
    for b in data:
        h = ((h ^ b) * FNV_PRIME_64) & MASK_64

    return h
