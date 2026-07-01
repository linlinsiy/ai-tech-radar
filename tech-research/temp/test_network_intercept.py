"""
网络拦截快速验证脚本 (短超时 + 实时进度)

使用 3 秒短超时，只测试 3~5 个代表性数据源，
每一步都实时打印，避免整批挂死。
"""
import os, sys, time, socket, asyncio
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "aws" / "app"))

from config import AWSConfig

TIMEOUT = 3  # 短超时，正常工作连接 3 秒足够

def fmt_ok(v):
    return " OK" if v else "FAIL"


def test_step(label, fn):
    """执行一个测试步骤并实时打印结果"""
    print(f"    {label:30s} ... ", end="", flush=True)
    try:
        ok, info, ms = fn()
        print(f"{fmt_ok(ok):>4s}  [{info[:60]}]  ({ms}ms)")
        return ok, info
    except Exception as e:
        print(f"FAIL  [{type(e).__name__}: {str(e)[:50]}]")
        return False, str(e)


# ---- 底层检测函数 ----

def test_dns(host):
    t0 = time.perf_counter()
    try:
        addrs = socket.getaddrinfo(host, 80, socket.AF_INET, socket.SOCK_STREAM)
        ip = addrs[0][4][0]
        return True, ip, int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return False, str(e)[:60], int((time.perf_counter() - t0) * 1000)

def test_tcp(host, port):
    t0 = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((host, port))
        s.close()
        return True, f"connected", int((time.perf_counter() - t0) * 1000)
    except socket.timeout:
        return False, "TCP timeout", int((time.perf_counter() - t0) * 1000)
    except OSError as e:
        winerr = f"WinError {e.winerror}" if hasattr(e, "winerror") else ""
        return False, f"{type(e).__name__} {winerr}"[:60], int((time.perf_counter() - t0) * 1000)

async def test_httpx_head_async(url):
    import httpx
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.head(url)
            return True, f"HTTP {r.status_code}", int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return False, f"{type(e).__name__}", int((time.perf_counter() - t0) * 1000)

def test_requests_head(url):
    import requests
    t0 = time.perf_counter()
    try:
        r = requests.head(url, timeout=TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": "AI-Radar-Test/1.0"})
        return True, f"HTTP {r.status_code}", int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return False, f"{type(e).__name__}", int((time.perf_counter() - t0) * 1000)


# ---- 主流程 ----
def main():
    config = AWSConfig(config_dir=str(_ROOT / "aws" / "config"))
    sources = config.get_data_sources()
    
    print("=" * 70)
    print(f"  网络拦截快速验证  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  timeout={TIMEOUT}s  |  数据源数量={len(sources)}")
    print("=" * 70)

    for i, src in enumerate(sources):
        url = src.get("access_url", "")
        host = urlparse(url).hostname if url else ""
        print(f"\n--- [{i+1}/12] {src['code']} ({host}) ---")
        
        if not host:
            print("    无有效 URL，跳过")
            continue
        
        # Step 1: DNS
        dns_ok, ip, _ = test_dns(host)
        print(f"    {'DNS 解析':30s} ... {fmt_ok(dns_ok):>4s}  [{ip[:40] if dns_ok else ip}]")
        
        if not dns_ok:
            continue
        
        # Step 2: TCP
        port = 443 if url.startswith("https") else 80
        tcp_ok, tcp_info, tcp_ms = test_tcp(ip, port)
        tcp_label = f"TCP {ip}:{port}"
        print(f"    {tcp_label:30s} ... {fmt_ok(tcp_ok):>4s}  [{tcp_info[:50]}]  ({tcp_ms}ms)")
        
        if not tcp_ok:
            # 尝试 80 端口
            if port == 443:
                tcp_ok2, tcp_info2, tcp_ms2 = test_tcp(ip, 80)
                print(f"    {'TCP ' + ip + ':80':30s} ... {fmt_ok(tcp_ok2):>4s}  [{tcp_info2[:50]}]  ({tcp_ms2}ms)")
        
        # Step 3: requests HEAD (先测这个更快)
        print(f"    {'requests.head':30s} ... ", end="", flush=True)
        try:
            import requests
            t0 = time.perf_counter()
            r = requests.head(url, timeout=TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "AI-Radar-Test/1.0"})
            ms = int((time.perf_counter() - t0) * 1000)
            print(f"{'OK':>4s}  [HTTP {r.status_code}] ({ms}ms)")
        except Exception as e:
            print(f"{'FAIL':>4s}  [{type(e).__name__}: {str(e)[:60]}]")
        
        # Step 4: httpx HEAD
        print(f"    {'httpx.AsyncClient.head':30s} ... ", end="", flush=True)
        try:
            ok, info, ms = asyncio.run(test_httpx_head_async(url))
            print(f"{fmt_ok(ok):>4s}  [{info}] ({ms}ms)")
        except Exception as e:
            print(f"{'FAIL':>4s}  [{type(e).__name__}: {str(e)[:60]}]")

    print("\n" + "=" * 70)
    print("  三个核心问题排查：")
    print("  1. DNS 全部 FAIL -> 公司 DNS 封禁，需配置内部 DNS 或代理")
    print("  2. DNS OK 但 TCP timeout -> 防火墙 DROP 出站 SYN 包")
    print("  3. DNS OK / TCP OK 但 HTTP 失败 -> SSL/HTTP 层拦截")
    print("=" * 70)

if __name__ == "__main__":
    main()
