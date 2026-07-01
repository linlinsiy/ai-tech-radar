# tech_insight/final_pipeline.py
"""
AI 技术趋势洞察机制 - 生产环境完全体 (Production Ready)

[V2.1.0 Refactored by Agent @ 2026-05-18]
- 配置文件分离 (config.py)
- 全面使用 requests 库处理网络请求
- 引入面向对象结构 (InsightPipeline class)
- 引入并发处理，大幅提升 RSS 抓取效率
- 支持多个火山知识库，并在一个满后自动切换到下一个
"""
import xml.etree.ElementTree as ET
import re
import json
import hashlib
import time
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.exceptions import RequestException
import urllib3

# 禁用 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 导入本地模块
import config
from l1_cluster import process_new_article
from volcengine_kb_uploader import VolcKnowledgeUploader, KnowledgeBaseFullError


class InsightPipeline:
    def __init__(self):
        self.fs_token = None
        self.processed_ids = set()
        # 初始化一次 Uploader，在整个运行过程中保持状态
        self.volc_uploader = VolcKnowledgeUploader()
        self.stats = {
            "new_l2": 0, "deleted_l2": 0, "promoted_l3": 0,
            "heat_increased_l1": 0, "heat_increased_topics": []
        }

    def _load_processed_ids(self):
        try:
            with open(config.DB_FILE, 'r') as f:
                self.processed_ids = set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            self.processed_ids = set()
            print("本地ID数据库不存在或为空，将全新开始。")

    def _save_processed_id(self, article_id):
        self.processed_ids.add(article_id)
        with open(config.DB_FILE, 'w') as f:
            json.dump(list(self.processed_ids), f, indent=4)

    def _get_feishu_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET}
        try:
            response = requests.post(url, json=payload, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            self.fs_token = response.json().get("tenant_access_token")
            if self.fs_token:
                print("✅ [Feishu] Token 获取完成")
            else:
                sys.exit("❌ [Feishu] Token 获取失败，响应中不含 token。")
        except RequestException as e:
            sys.exit(f"❌ [Feishu] Token 获取失败，网络请求异常: {e}")

    def _call_llm(self, prompt, model_type="light", max_retries=2):
        # 主模型: Gemini
        gemini_model_name = config.GEMINI_LIGHT_MODEL if model_type == "light" else config.GEMINI_PRO_MODEL
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model_name}:generateContent?key={config.GEMINI_API_KEY}"
        gemini_headers = {"Content-Type": "application/json"}
        gemini_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}
        }

        # Fallback 模型: Volcengine
        volc_model_name = config.VOLC_FALLBACK_MODEL
        volc_url = "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions"
        volc_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.VOLC_API_KEY}"
        }
        volc_payload = {
            "model": volc_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        # 重试与 Fallback 逻辑
        for attempt in range(max_retries):
            try:
                # 优先尝试主模型
                response = requests.post(gemini_url, json=gemini_payload, headers=gemini_headers, timeout=90, verify=False)
                response.raise_for_status()
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    text_response = result['candidates'][0]['content']['parts'][0]['text']
                    if text_response.startswith("```json"):
                        text_response = text_response[7:-3].strip()
                    return json.loads(text_response)
                else:
                    raise ValueError(f"Gemini 响应格式异常: {result}")
            except (RequestException, ValueError, json.JSONDecodeError) as e:
                print(f"   ❌ [主模型失败] {gemini_model_name} 调用失败 (第 {attempt + 1} 次): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3) # 重试前等待
                    continue
                else:
                    # 主模型重试耗尽，触发 Fallback
                    print(f"   🌋 [触发 Fallback] 主模型彻底失败，切换到 {volc_model_name}...")
                    try:
                        response = requests.post(volc_url, json=volc_payload, headers=volc_headers, timeout=90, verify=False)
                        response.raise_for_status()
                        result = response.json()
                        text_response = result['choices'][0]['message']['content']
                        
                        if text_response.startswith("```json"):
                           text_response = text_response[7:-3].strip()
                        return json.loads(text_response)
                    except (RequestException, ValueError, json.JSONDecodeError, KeyError) as e_fallback:
                        print(f"   ❌ [Fallback 失败] {volc_model_name} 也调用失败: {e_fallback}")
                        return None
        return None

    def _write_to_feishu_l2(self, article_data):
        # ... (此方法保持不变)
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{config.FEISHU_TABLE_L2}/records"
        headers = {"Authorization": f"Bearer {self.fs_token}", "Content-Type": "application/json"}
        try:
            pub_date_ms = int(parsedate_to_datetime(article_data["pub_date"]).timestamp() * 1000)
        except (TypeError, ValueError):
            pub_date_ms = int(time.time() * 1000)
        fields = {
            "文章标题": article_data["zh_title"],"原文链接": {"link": article_data["link"], "text": "点击访问原文"},
            "AI分类": article_data["ai_category"],"AI打分": article_data["ai_score"],
            "一句话快讯": article_data["clean_summary"],"技术标签": article_data["tech_tags"],
            "涉及大厂": article_data["involved_companies"],"处理状态": article_data["process_status"],
            "发布时间": pub_date_ms
        }
        try:
            response = requests.post(url, headers=headers, json={"fields": fields}, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            return response.json()["data"]["record"]["record_id"]
        except RequestException as e:
            print(f"   ❌ 写入 L2 失败: {e.response.text if e.response else e}")
            return None

    def _write_to_feishu_l3(self, l3_data, l2_record_id, article_pub_date_ms):
        # ... (此方法保持不变)
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{config.FEISHU_TABLE_L3}/records"
        headers = {"Authorization": f"Bearer {self.fs_token}", "Content-Type": "application/json"}
        action_items = l3_data.get("Action_Items", "")
        if isinstance(action_items, list):
            action_items = "\n".join([f"- {item}" for item in action_items])
        fields = {
            "关联L2文章标题": [l2_record_id],"核心痛点": l3_data.get("Context_And_Problem", ""),
            "技术实现": l3_data.get("Tech_Implementation", ""),"量化指标": l3_data.get("Metrics_And_Results", ""),
            "行动建议": action_items,"发布时间": article_pub_date_ms
        }
        try:
            response = requests.post(url, headers=headers, json={"fields": fields}, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"   ❌ 写入 L3 失败: {e.response.text if e.response else e}")
            return False

    def _delete_l2_record(self, record_id):
        # ... (此方法保持不变)
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{config.FEISHU_TABLE_L2}/records/{record_id}"
        headers = {"Authorization": f"Bearer {self.fs_token}"}
        try:
            response = requests.delete(url, headers=headers, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"   ❌ 删除L2记录失败: {e}")
            return False

    def _fetch_full_article_text(self, url):
        # ... (此方法保持不变)
        try:
            headers = {'User-Agent': config.USER_AGENT}
            response = requests.get(url, headers=headers, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            html = response.text
            body_start = html.find('<body')
            body_end = html.find('</body>', body_start if body_start != -1 else 0)
            body_content = html[body_start if body_start != -1 else 0 : body_end if body_end != -1 else len(html)]
            text = re.sub(r'<script.*?</script>|<style.*?</style>', '', body_content, flags=re.DOTALL|re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            return re.sub(r'\s+', ' ', text).strip()
        except RequestException as e:
            print(f"   ⚠️  全文提取失败 (RequestException): {e}")
            return None

    def _sync_to_volc_kb(self, l2_record_id, l2_result, pub_date_ms, link, l3_result=None):
        """
        将文章同步到火山知识库，并在当前知识库满时自动切换到下一个。
        """
        if not l2_record_id:
            return

        while True:
            try:
                l3_context, l3_tech, l3_metrics, l3_action = None, None, None, None
                if l3_result:
                    l3_context = l3_result.get("Context_And_Problem")
                    l3_tech = l3_result.get("Tech_Implementation")
                    l3_metrics = l3_result.get("Metrics_And_Results")
                    l3_action = l3_result.get("Action_Items")
                    if isinstance(l3_action, list):
                        l3_action = "\n".join([f"- {item}" for item in l3_action])
                
                self.volc_uploader.create_document(
                    l2_id=l2_record_id, zh_title=l2_result["zh_title"],
                    clean_summary=l2_result["clean_summary"], ai_score=l2_result["ai_score"],
                    ai_category=l2_result["ai_category"], tech_tags=l2_result["tech_tags"],
                    involved_companies=l2_result["involved_companies"],
                    publish_timestamp=int(pub_date_ms / 1000),
                    context_and_problem=l3_context, tech_implementation=l3_tech,
                    metrics_and_results=l3_metrics, action_items=l3_action,
                    original_url=link
                )
                break  # 上传成功，跳出循环

            except KnowledgeBaseFullError as e:
                print(f"   ⚠️  [KB Sync] {e}")
                print("   ↪️  尝试切换到下一个知识库...")
                if not self.volc_uploader.switch_to_next_kb():
                    print("   ❌ [KB Sync] 所有知识库均已满，停止同步该文章。")
                    break
            except Exception as e:
                print(f"   ❌ [KB Sync] 同步到火山知识库时发生未知错误: {e}")
                break

    def _process_article(self, item):
        title = item.findtext('title', default="").strip()
        link = item.findtext('link', default="").strip()
        if not link: return

        article_id = hashlib.md5(link.encode('utf-8')).hexdigest()
        if article_id in self.processed_ids: return

        print(f"   🆕 [发现增量文章] {title[:50]}...")
        
        pub_date = item.findtext('pubDate', default="").strip()
        desc = item.findtext('description', default="").strip()
        clean_desc = re.sub('<[^<]+>', '', desc)[:1500]
        
        l2_prompt = f"""你是一名资深中文 IT 技术主编。请评估以下全英文文章的研发落地价值，并严格输出 JSON 格式。
        注意：所有输出字段必须使用地道专业的中文！

        【英文原文信息】
        标题：{title}
        摘要：{clean_desc}

        【强制 JSON 输出格式】
        {{
            "zh_title": "(翻译为地道的中文技术标题)",
            "ai_score": (1-10分，8分以上必须是硬核架构或重大开源),
            "ai_category": "(落地案例/开源组件/学术论文/行业快讯)",
            "clean_summary": "(50-80字极简全中文摘要，提炼核心价值)",
            "tech_tags": ["RAG", "微服务", "大模型", ...],
            "involved_companies": ["AWS", "Netflix", ...]
        }}
        """
        l2_result = self._call_llm(l2_prompt, model_type="light")
        if not l2_result:
            self._save_processed_id(article_id); return

        l2_result.update({"link": link, "pub_date": pub_date})
        score = l2_result.get("ai_score", 0)
        l2_result["process_status"] = "已晋级L3" if score >= config.L3_PROMOTION_SCORE else "止步快讯"
        print(f"   📝 [L2结果] 译名: {l2_result.get('zh_title', title)[:30]} | 打分: {score} | 状态: {l2_result['process_status']}")
        
        l2_record_id = self._write_to_feishu_l2(l2_result)
        if not l2_record_id:
            self._save_processed_id(article_id); return
        self.stats["new_l2"] += 1
        
        try:
            pub_date_ms = int(parsedate_to_datetime(pub_date).timestamp() * 1000)
        except (TypeError, ValueError):
            pub_date_ms = int(time.time() * 1000)
        
        article_data = {"文章标题": l2_result["zh_title"], "一句话快讯": l2_result["clean_summary"], "l2_record_id": l2_record_id, "AI打分": score, "链接": link, "发布时间": pub_date_ms}
        try:
            should_keep, l1_cluster_id, topic_name = process_new_article(self.fs_token, article_data)
            if l1_cluster_id and topic_name and topic_name not in self.stats["heat_increased_topics"]:
                self.stats["heat_increased_l1"] += 1; self.stats["heat_increased_topics"].append(topic_name)
        except Exception as e:
            print(f"   ❌ L1聚类发生异常: {e}"); should_keep = True

        if not should_keep:
            print("   ⏭️  [L1去重] 同一事件已有更高质量文章，删除当前L2记录。")
            self._delete_l2_record(l2_record_id); self.stats["deleted_l2"] += 1
            self._save_processed_id(article_id); return

        l3_result = None
        if score >= config.L3_PROMOTION_SCORE:
            print(f"   🔥 [高潜拦截] 触发 L3 深度精读 ({config.GEMINI_PRO_MODEL})...")
            full_text = self._fetch_full_article_text(link)
            text_content = f"Title: {title}\n\nContent: {clean_desc}" if not full_text or len(full_text.strip()) < 200 else f"Title: {title}\n\nContent: {full_text[:config.MAX_ARTICLE_LENGTH]}"
            l3_prompt = f'你现在是首席架构师...【正文内容】：\n{text_content}'
            l3_result = self._call_llm(l3_prompt, model_type="pro")
            if l3_result and self._write_to_feishu_l3(l3_result, l2_record_id, pub_date_ms):
                self.stats["promoted_l3"] += 1
        
        self._save_processed_id(article_id)
        self._sync_to_volc_kb(l2_record_id, l2_result, pub_date_ms, link, l3_result)
        time.sleep(2)

    def _process_source(self, source_info):
        source, url = source_info
        print(f"\n📡 正在抓取: {source}")
        sys.stdout.flush()
        try:
            response = requests.get(url, headers={'User-Agent': config.USER_AGENT}, timeout=config.REQUESTS_TIMEOUT, verify=False)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            items = root.findall('.//item')[:config.MAX_ARTICLES_PER_SOURCE]
            for item in items: self._process_article(item)
        except (RequestException, ET.ParseError) as e:
            print(f"   ❌ 源处理失败 ({source}): {e}")
        sys.stdout.flush()

    def run(self):
        print("🚀 [System] 启动生产环境流水线 (V2.1)...")
        self._load_processed_ids()
        self._get_feishu_token()
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self._process_source, config.RSS_SOURCES.items())
        self._print_summary()

    def _print_summary(self):
        print("\n" + "="*50)
        print("📊 [流水线运行完成统计汇总]")
        print(f"  本次新增 L2 记录: {self.stats['new_l2']} 条")
        print(f"  因相似度去重删除: {self.stats['deleted_l2']} 条")
        print(f"  成功晋升 L3: {self.stats['promoted_l3']} 条")
        print(f"  L1 表热度增加: {self.stats['heat_increased_l1']} 条")
        if self.stats['heat_increased_topics']:
            print("  热度增加的事件主题:")
            for topic in self.stats['heat_increased_topics']:
                print(f"    • {topic}")
        print("="*50 + "\n")

if __name__ == "__main__":
    pipeline = InsightPipeline()
    pipeline.run()
