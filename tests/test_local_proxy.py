"""Local VPN compatibility must not turn off the private-address guard."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from app.config import Settings
from app.safety import friendly_error, is_public_ip, local_proxy_url, network_guard
import start

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('value,expected', [
    ('', ''), ('http://127.0.0.1:9876', 'http://127.0.0.1:9876'),
    ('http://localhost:9876/', 'http://127.0.0.1:9876'),
    ('socks5h://[::1]:9876', 'socks5h://[::1]:9876'),
])
def test_explicit_local_proxy_is_canonical(value, expected):
    assert local_proxy_url(value) == expected


@pytest.mark.parametrize('value', [
    'http://proxy.example:9876', 'http://192.168.1.1:9876', 'http://198.18.0.1:9876',
    'http://127.0.0.1', 'http://127.0.0.1:0', 'http://127.0.0.1:65536',
    'http://user:pass@127.0.0.1:9876', 'http://127.0.0.1:9876/relay',
    'http://127.0.0.1:9876?url=test', 'http://127.0.0.1:9876#fragment',
    'file://127.0.0.1:9876', 'http://localhost.evil.example:9876',
    'http://127.0.0.1:9876\n',
])
def test_local_mode_does_not_accept_remote_or_ambiguous_proxies(value):
    with pytest.raises(ValueError):
        local_proxy_url(value)
    with pytest.raises(RuntimeError):
        Settings(local_device=True, proxy=value).validate()


def test_launcher_only_uses_this_explicit_local_option(monkeypatch):
    monkeypatch.setenv('YTDLP_PROXY', 'https://old-hosting.example:8888')
    monkeypatch.setenv('CLIPNEST_LOCAL_PROXY', 'http://127.0.0.1:1111')
    start.configure_local_device('127.0.0.1', 'http://localhost:9876')
    assert os.environ['YTDLP_PROXY'] == ''
    assert os.environ['CLIPNEST_LOCAL_PROXY'] == 'http://127.0.0.1:9876'
    env = {**os.environ, 'CLIPNEST_WORKER': '1'}
    script = 'import json; from app.config import settings; print(json.dumps([settings.local_device, settings.proxy]))'
    result = subprocess.check_output([sys.executable, '-c', script], cwd=ROOT, env=env, text=True)
    assert json.loads(result) == [True, 'http://127.0.0.1:9876']
    start.configure_local_device('127.0.0.1')
    assert os.environ['CLIPNEST_LOCAL_PROXY'] == '', 'A future launch must not retain an old local proxy'


def test_fake_ip_remains_blocked_with_a_specific_actionable_error(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k:
        [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('198.18.0.6', 443))])
    assert not is_public_ip('198.18.0.6')
    with network_guard():
        with pytest.raises(OSError) as caught:
            socket.getaddrinfo('x.com', 443)
        assert friendly_error(str(caught.value))[0] == 'LOCAL_PROXY_REQUIRED'
        with socket.socket() as sock:
            with pytest.raises(OSError, match='virtual DNS'):
                sock.connect(('198.19.1.2', 443))
    assert friendly_error('Blocked network request to private address')[0] == 'UNSAFE_TARGET'


def test_proxy_exception_is_one_endpoint_not_all_private_connections(monkeypatch):
    def dns(host, port, *args, **kwargs):
        ip = '127.0.0.1' if host == '127.0.0.1' else '198.18.0.6'
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
    connections = []
    monkeypatch.setattr(socket, 'getaddrinfo', dns)
    monkeypatch.setattr(socket.socket, 'connect', lambda self, address: connections.append(address))
    with network_guard('http://127.0.0.1:9876'), socket.socket() as sock:
        sock.connect(('127.0.0.1', 9876))
        for address in [('127.0.0.1', 22), ('169.254.169.254', 80), ('192.168.1.1', 80), ('198.18.0.6', 443)]:
            with pytest.raises(OSError):
                sock.connect(address)
        with pytest.raises(OSError):
            socket.getaddrinfo('x.com', 443)
    assert connections == [('127.0.0.1', 9876)]
