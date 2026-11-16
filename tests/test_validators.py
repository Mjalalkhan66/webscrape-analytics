import pytest

from utils import validators
from utils.helpers import normalize_url, same_site
from utils.validators import URLValidationError, validate_url


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    table = {"example.com": ["93.184.216.34"], "evil.test": ["10.0.0.5"], "mixed.test": ["93.184.216.34", "127.0.0.1"],
             "decimal": ["127.0.0.1"], "2130706433": ["127.0.0.1"]}

    def fake_getaddrinfo(host, port, proto=0):
        if host not in table:
            import socket
            raise socket.gaierror("nope")
        return [(2, 1, 6, "", (ip, port)) for ip in table[host]]
    monkeypatch.setattr(validators.socket, "getaddrinfo", fake_getaddrinfo)


def test_valid_url_is_normalised():
    assert validate_url("HTTPS://Example.com/Path?q=1#frag") == "https://example.com/Path?q=1"


def test_scheme_added_when_missing():
    assert validate_url("example.com") == "https://example.com/"


@pytest.mark.parametrize("url", [
    "ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "data:text/html,hi", "", "   ",
    "http://localhost/", "http://127.0.0.1/", "http://[::1]/", "http://10.1.2.3/", "http://192.168.0.1/",
    "http://169.254.169.254/latest/meta-data/", "http://172.16.0.1/", "http://0.0.0.0/", "http://[::ffff:127.0.0.1]/",
    "http://user:pw@example.com/", "http://example.com:22/", "http://intranet.local/", "http://nodots/",
    "http://evil.test/", "http://mixed.test/", "http://2130706433/", "http://example.com/a b",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(URLValidationError):
        validate_url(url)


def test_unresolvable_host():
    with pytest.raises(URLValidationError):
        validate_url("https://doesnotexist.example.invalid")


def test_helpers():
    assert normalize_url("HTTP://Example.com:80/a#x") == "http://example.com/a"
    assert same_site("www.example.com", "example.com")
    assert not same_site("a.com", "b.com")
