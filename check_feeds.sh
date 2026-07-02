#!/bin/bash
# ============================================================
# AI技术趋势雷达 - RSS Feed 连通性检查脚本
# 用法: bash check_feeds.sh
# ============================================================

# 前置检查
if ! command -v curl &>/dev/null; then
  echo "❌ curl 未安装，请先执行: apt install -y curl (或 yum install -y curl)"
  exit 1
fi

urls=(
  "http://export.arxiv.org/rss/cs.AI"
  "http://googleresearch.blogspot.com/atom.xml"
  "https://deepmind.com/blog/feed/basic/"
  "https://rsshub.app/openai/blog"
  "https://huggingface.co/blog/feed.xml"
  "https://engineering.fb.com/feed/"
  "http://bair.berkeley.edu/blog/feed.xml"
  "https://lastweekin.ai/feed/"
  "https://rsshub.bestblogs.dev/deeplearning/thebatch"
  "https://www.jiqizhixin.com/rss"
  "https://www.qbitai.com/feed"
  "https://aws.amazon.com/blogs/machine-learning/feed/"
  "https://werss.bestblogs.dev/feeds/MP_WXS_3554086560.atom"
  "https://dev.to/feed/tag/ai"
  "https://blog.langchain.dev/rss/"
)

echo "========================================"
echo "  AI Radar - Feed Connectivity Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

ok=0
fail=0

for url in "${urls[@]}"; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 15 "$url" 2>/dev/null) || code="000"
  if [ "$code" = "200" ]; then
    echo "✅  $code  $url"
    ok=$((ok + 1))
  else
    echo "❌  $code  $url"
    fail=$((fail + 1))
  fi
done

echo ""
echo "========================================"
echo "  Result: $ok OK, $fail FAIL"
echo "========================================"
