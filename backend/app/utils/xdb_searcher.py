# -*- coding: utf-8 -*-
"""
ip2region v4 pure-python xdb reader
Adapted from Lionsoul ip2region (Apache 2.0 License).
Completely self-contained with zero third-party dependencies.
"""
import io
import os
import socket
import struct

HeaderInfoLength = 256
VectorIndexRows = 256
VectorIndexCols = 256
VectorIndexSize = 8
VectorIndexLength = 524288  # 256 * 256 * 8


def _le_uint16(b, offset):
    return b[offset] | (b[offset + 1] << 8)


def _le_uint32(b, offset):
    return (
        b[offset]
        | (b[offset + 1] << 8)
        | (b[offset + 2] << 16)
        | (b[offset + 3] << 24)
    )


class XdbSearcher(object):
    """
    In-memory content-buffered xdb searcher for sub-microsecond IP lookups.
    """
    def __init__(self, c_buffer: bytes):
        if len(c_buffer) < HeaderInfoLength + VectorIndexLength:
            raise ValueError("invalid xdb content buffer: too short")
        self.c_buffer = c_buffer

    @classmethod
    def load_from_file(cls, db_path: str):
        with io.open(db_path, "rb") as f:
            c_buffer = f.read()
        return cls(c_buffer)

    def search(self, ip_str: str) -> str:
        """
        Search an IPv4 address and return raw region string (e.g. '中国|北京市|北京市|电信|CN')
        Returns empty string if not found, invalid, or upon any parsing error.
        """
        if not ip_str or not isinstance(ip_str, str):
            return ""

        try:
            ip_bytes = socket.inet_aton(ip_str.strip())
            if len(ip_bytes) != 4:
                return ""

            buff_len = len(self.c_buffer)
            i0, i1 = ip_bytes[0], ip_bytes[1]
            offset = HeaderInfoLength + (i0 * VectorIndexCols * VectorIndexSize) + (i1 * VectorIndexSize)
            if offset + 8 > buff_len:
                return ""

            s_ptr = _le_uint32(self.c_buffer, offset)
            e_ptr = _le_uint32(self.c_buffer, offset + 4)

            if s_ptr == 0 or e_ptr == 0 or s_ptr >= e_ptr or e_ptr > buff_len:
                return ""

            index_size = 14  # IPv4 index entry size: 4 bytes start_ip + 4 bytes end_ip + 2 bytes data_len + 4 bytes data_ptr
            l, h = 0, int((e_ptr - s_ptr) / index_size)
            d_len, d_ptr = 0, 0

            target_ip = struct.unpack("!I", ip_bytes)[0]

            while l <= h:
                m = (l + h) >> 1
                p = int(s_ptr + m * index_size)
                if p + index_size > buff_len:
                    break

                buff = self.c_buffer[p:p + index_size]
                sip = _le_uint32(buff, 0)
                if target_ip < sip:
                    h = m - 1
                else:
                    eip = _le_uint32(buff, 4)
                    if target_ip > eip:
                        l = m + 1
                    else:
                        d_len = _le_uint16(buff, 8)
                        d_ptr = _le_uint32(buff, 10)
                        break

            if d_len == 0 or d_ptr + d_len > buff_len:
                return ""

            return self.c_buffer[d_ptr:d_ptr + d_len].decode("utf-8", errors="ignore")
        except Exception:
            return ""
