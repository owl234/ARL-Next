"""Bounded favicon GETs with address validation and DNS pinning."""

import ipaddress
import logging
import socket
import ssl
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit, urlunsplit

import urllib3

logger = logging.getLogger(__name__)


def fetch_favicon_response(url, *, allowed_ip, forbidden_domain, proxy_url=''):
    parsed = urlsplit(url)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or '\\' in url or any(ord(c) < 32 for c in url)):
        raise ValueError('Unsupported favicon URL')
    host = parsed.hostname.encode('idna').decode('ascii')
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
    if not 1 <= port <= 65535 or forbidden_domain(host):
        raise ValueError('Forbidden favicon target')
    addresses = []
    for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(entry[4][0])
        address = getattr(address, 'ipv4_mapped', None) or address
        if (address.is_loopback or address.is_link_local or address.is_unspecified
                or address.is_multicast or not allowed_ip(str(address))):
            raise ValueError('Favicon target resolves to a forbidden address')
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError('Favicon target has no usable address')

    # Connect to the checked literal address; do not resolve the hostname again.
    address = addresses[0]
    authority = f'[{address}]' if address.version == 6 else str(address)
    pinned_url = urlunsplit((parsed.scheme, f'{authority}:{port}', parsed.path or '/', parsed.query, ''))
    original_host = f'[{host}]' if ':' in host else host
    headers = {'Host': f'{original_host}:{port}', 'User-Agent': 'ARL-Next/favicon',
               'Accept-Encoding': 'identity', 'Connection': 'close'}
    pool_options = {'timeout': urllib3.Timeout(connect=10, read=10), 'retries': False}
    if parsed.scheme == 'https':
        # Self-signed certificates are expected on scanned assets. Preserve SNI.
        pool_options.update(cert_reqs=ssl.CERT_NONE, assert_hostname=False, server_hostname=host)
    if proxy_url:
        raw_proxy = str(proxy_url).strip()
        lower_proxy = raw_proxy.lower()
        if lower_proxy.startswith('socks'):
            try:
                from urllib3.contrib.socks import SOCKSProxyManager
                p_socks = urlsplit(raw_proxy)
                socks_kwargs = {}
                clean_proxy = raw_proxy
                if p_socks.username is not None or p_socks.password is not None:
                    if p_socks.username is not None:
                        socks_kwargs['username'] = unquote(p_socks.username)
                    if p_socks.password is not None:
                        socks_kwargs['password'] = unquote(p_socks.password)
                    host_fmt = f'[{p_socks.hostname}]' if p_socks.hostname and ':' in p_socks.hostname else (p_socks.hostname or '')
                    netloc = f'{host_fmt}:{p_socks.port}' if p_socks.port else host_fmt
                    clean_proxy = urlunsplit((p_socks.scheme, netloc, p_socks.path, p_socks.query, ''))
                manager = SOCKSProxyManager(clean_proxy, **socks_kwargs, **pool_options)
            except Exception as exc:
                logger.warning("SOCKSProxyManager initialization failed for favicon fetch (%s); falling back to direct", exc)
                manager = urllib3.PoolManager(**pool_options)
        else:
            manager = urllib3.ProxyManager(raw_proxy, **pool_options)
    else:
        manager = urllib3.PoolManager(**pool_options)
    response = None
    try:
        response = manager.request('GET', pinned_url, headers=headers, redirect=False,
                                   preload_content=False)
        limit = 2 * 1024 * 1024
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('Favicon exceeds 2MB')
        return SimpleNamespace(status_code=response.status, headers=response.headers, content=content)
    finally:
        if response is not None:
            response.close()
        manager.clear()
