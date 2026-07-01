import sys, os
sys.path.insert(0, r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app")
os.chdir(r"D:\013148\code\AI技术趋势雷达\tech-research\aws")
os.environ["AI_RADAR_CONFIG_DIR"] = r"./config"
from config import AWSConfig
import asyncio, httpx, time

config = AWSConfig()
sources = config.get_data_sources()
print(f"Total sources: {len(sources)}")

async def test():
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for src in sources[:3]:
            domain = src.get("domain", "")
            access_url = src.get("access_url", "")
            url = access_url or f"https://{domain}" if domain else ""
            print(f"{src['code']}: access_url=[{str(access_url)[:80]}]")
            try:
                start = time.time()
                resp = await client.head(url)
                print(f"  OK {resp.status_code} ({(time.time()-start)*1000:.0f}ms)")
            except Exception as e:
                print(f"  FAIL type={type(e).__name__} str=[{str(e)}]")

asyncio.run(test())
