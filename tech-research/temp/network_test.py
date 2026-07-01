import socket, asyncio, httpx, time
from urllib.parse import urlparse

TARGETS = [
    ("wechat2rss-xin-zhi-yuan", "https://wechat2rss.bestblogs.dev/"),
    ("qbitai", "https://www.qbitai.com/"),
    ("arxiv", "http://export.arxiv.org/rss/cs.AI"),
    ("aws-ml-blog", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("infoq", "https://feed.infoq.com/ai-ml-data-eng/news"),
    ("hackernews", "https://hnrss.org/"),
    ("huggingface", "https://huggingface.co/"),
    ("netflix-techblog", "https://netflixtechblog.com/"),
    ("invalid-domain", "https://this-domain-does-not-exist-12345.com/"),
]
INTERNAL_URL = "http://168.63.65.40:8090/llm-service/v1/models"
TIMEOUT = 5

def test_dns(host):
    start = time.time()
    try:
        addr = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
        ip = addr[0][4][0] if addr else "no-address"
        return True, ip, int((time.time()-start)*1000)
    except Exception as e:
        return False, str(e)[:60], int((time.time()-start)*1000)

def test_tcp(host, port=443):
    start = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        s.connect((host, port))
        s.close()
        return True, f"port {port} open", int((time.time()-start)*1000)
    except socket.timeout:
        return False, "TCP timeout", int((time.time()-start)*1000)
    except ConnectionRefusedError:
        return False, "refused", int((time.time()-start)*1000)
    except OSError as e:
        return False, f"{type(e).__name__}", int((time.time()-start)*1000)
    except Exception as e:
        return False, f"{type(e).__name__}", int((time.time()-start)*1000)

async def test_http(url):
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, trust_env=False) as c:
            r = await c.get(url)
            return True, f"HTTP {r.status_code}", int((time.time()-start)*1000)
    except httpx.ConnectTimeout:
        return False, "ConnectTimeout", int((time.time()-start)*1000)
    except httpx.ConnectError as e:
        return False, f"ConnectError", int((time.time()-start)*1000)
    except Exception as e:
        return False, f"{type(e).__name__}", int((time.time()-start)*1000)

print("=" * 70)
print("  Network Connectivity Test")
print("=" * 70)
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}  Timeout: {TIMEOUT}s")
print()
print(f"{'Target':28s} {'Host':38s} DNS       TCP       HTTPS")
print("-" * 100)

any_external_ok = False

for name, url in TARGETS:
    p = urlparse(url)
    host = p.hostname or ""
    
    dns_ok, dns_info, dns_ms = test_dns(host)
    
    if dns_ok:
        tcp_ok, tcp_info, tcp_ms = test_tcp(dns_info, 443)
    else:
        tcp_ok, tcp_info, tcp_ms = False, "DNS failed", 0
    
    http_ok, http_info, http_ms = asyncio.run(test_http(url))
    
    if http_ok:
        any_external_ok = True
    
    dns_s = "OK" if dns_ok else "FAIL"
    tcp_s = "OK" if tcp_ok else "FAIL"
    http_s = "OK" if http_ok else "FAIL"
    print(f"  {name:26s} {host:38s} {dns_s:4s} {dns_ms:>4}ms  {tcp_s:4s} {tcp_ms:>4}ms  {http_s:4s} {http_info}")

print()
print("=" * 70)
print("  Internal Network Check")
print("=" * 70)
p = urlparse(INTERNAL_URL)
host = p.hostname
dns_ok, dns_info, dns_ms = test_dns(host) if host else (False, "no host", 0)
http_ok, http_info, http_ms = asyncio.run(test_http(INTERNAL_URL))
print(f"  LLM: {INTERNAL_URL}")
print(f"    DNS: {'OK' if dns_ok else 'FAIL'} ({dns_ms}ms)  HTTP: {'OK' if http_ok else 'FAIL'} {http_info} ({http_ms}ms)")

print()
print("=" * 70)
print("  Verdict")
print("=" * 70)
if http_ok and not any_external_ok:
    print("  Corporate firewall blocks outbound TCP to internet.")
    print("  DNS ok, TCP connect to port 443 all timeout.")
    print("  Deploy AWS side on a node with internet access.")
elif http_ok and any_external_ok:
    print("  Some external URLs reachable, network partial ok.")
elif not http_ok:
    print("  Even internal LLM unreachable - local network issue.")
