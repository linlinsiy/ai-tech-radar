"""
AWS 侧配置加载模块

从 config/config.properties 读取所有配置项，支持数据源索引格式
（如 data_sources[0].code），提供类型安全的数据源列表和模型配置访问。

读取路径：./config/config.properties
机密信息通过 secrets/.env 环境变量注入，不写入 properties 文件。
"""
import configparser
import os
from datetime import datetime
from typing import List, Dict, Optional


class AWSConfig:
    """
    AWS 侧全局配置管理器

    加载 config.properties 并解析数据源索引格式，提供结构化配置访问。
    所有属性名与 config.properties 中的键名保持一致。

    类变量：
        _instance: 单例实例
        _config: configparser 解析结果
        _config_dir: 配置文件目录绝对路径
    """

    _instance: Optional["AWSConfig"] = None

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器

        入参：
            config_dir: 配置文件目录，默认为 ./config
        """
        if config_dir is None:
            config_dir = os.environ.get("AI_RADAR_CONFIG_DIR", "./config")
        self._config_dir = config_dir
        self._config = configparser.ConfigParser()
        self._load()

    @classmethod
    def get_instance(cls, config_dir: Optional[str] = None) -> "AWSConfig":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    def _load(self):
        """加载 config.properties 和 secrets/.env"""
        props_path = os.path.join(self._config_dir, "config.properties")
        if os.path.exists(props_path):
            self._config.read(props_path, encoding="utf-8")
        # 加载环境变量（API Key 等敏感信息）
        env_path = os.path.join(
            os.path.dirname(self._config_dir), "secrets", ".env"
        )
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()

        # 将代理配置注入环境变量，使 urllib / requests / feedparser 等库自动走公司代理
        proxy_url = self.proxy_url
        if proxy_url:
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            bypass = self.get(option='proxy.bypass', fallback='')
            if bypass:
                os.environ['NO_PROXY'] = bypass

    def get(self, section: str = "DEFAULT", option: str = "", fallback: str = "") -> str:
        """
        读取单个配置项

        入参：
            section: 配置段，默认 DEFAULT
            option: 配置项键名
            fallback: 默认值
        出参：配置值字符串
        """
        return self._config.get(section, option, fallback=fallback)

    def get_int(self, option: str, fallback: int = 0) -> int:
        """读取整数配置项"""
        return self._config.getint("DEFAULT", option, fallback=fallback)

    def get_float(self, option: str, fallback: float = 0.0) -> float:
        """读取浮点数配置项"""
        return self._config.getfloat("DEFAULT", option, fallback=fallback)

    # === 数据源访问 ===

    def get_data_sources(self) -> List[Dict[str, str]]:
        """
        获取所有启用的数据源列表

        出参：数据源字典列表，每项包含 code/name/type/access_url/domain/fetch_method。
        对 HTML 爬虫等扩展配置，保留 data_sources[N].* 的所有附加键。
        """
        count = self.get_int("data_sources.count")
        sources = []
        for i in range(count):
            enabled = self._config.get(
                "DEFAULT", f"data_sources[{i}].enabled", fallback="true"
            )
            if enabled.lower() != "true":
                continue
            prefix = f"data_sources[{i}]."
            source = {}
            for key, value in self._config.items("DEFAULT"):
                if key.startswith(prefix):
                    source[key[len(prefix):]] = value
            if not source.get("selection_role"):
                source["selection_role"] = self._default_selection_role(
                    source.get("type", "")
                )
            sources.append(source)
        return sources

    @staticmethod
    def _default_selection_role(source_type: str) -> str:
        """Populate the legacy source analysis role for import compatibility."""
        normalized = str(source_type or "").strip()
        if normalized == "academic":
            return "research"
        if normalized in {"tech_media", "industry_application", "regulator"}:
            return "industry"
        return "engineering"

    # === 模型配置 ===

    @property
    def l2_model(self) -> Dict[str, str]:
        """L2 基础分析模型配置"""
        return {
            "provider": self.get(option="l2_model.provider"),
            "model": self.get(option="l2_model.model"),
            "temperature": self.get_float("l2_model.temperature", 0.3),
            "max_tokens": self.get_int("l2_model.max_tokens", 2048),
            "timeout_seconds": self.get_int("l2_model.timeout_seconds", 120),
            "max_concurrency": self.get_int("l2_model.max_concurrency", 3),
            "max_retries": self.get_int("l2_model.max_retries", 0),
        }

    @property
    def l3_model(self) -> Dict[str, str]:
        """L3 深度洞察模型配置"""
        return {
            "provider": self.get(option="l3_model.provider"),
            "model": self.get(option="l3_model.model"),
            "temperature": self.get_float("l3_model.temperature", 0.3),
            "max_tokens": self.get_int("l3_model.max_tokens", 4096),
            "timeout_seconds": self.get_int("l3_model.timeout_seconds", 300),
            "max_concurrency": self.get_int("l3_model.max_concurrency", 1),
            "max_retries": self.get_int("l3_model.max_retries", 0),
        }

    # === 导入接口配置 ===

    @property
    def scheduler_config(self) -> Dict[str, str]:
        """调度模式配置"""
        mode = self.get(option="scheduler.mode", fallback="xxljob").strip().lower()
        if mode not in ("xxljob", "crontab", "none"):
            mode = "xxljob"
        return {
            "mode": mode,
            "cron_collect": self.get(option="scheduler.cron.collect", fallback="0 8 * * *"),
            "cron_health_check": self.get(option="scheduler.cron.health_check", fallback="*/30 * * * *"),
        }

    @property
    def import_endpoint_url(self) -> str:
        """内部受控导入接口地址"""
        return self.get(option="import_endpoint.url")

    @property
    def import_retry_config(self) -> Dict:
        """导入重试配置"""
        backoff = self.get(option="import_endpoint.retry_backoff_seconds", fallback="10,30")
        return {
            "timeout_seconds": self.get_int("import_endpoint.timeout_seconds", 30),
            "retry_max": self.get_int("import_endpoint.retry_max", 2),
            "backoff_seconds": [int(s.strip()) for s in backoff.split(",")],
        }

    # === L3 触发条件 ===

    @property
    def deep_insight_min_score(self) -> float:
        """L3 深度洞察触发最低评分"""
        configured = self.get(option="deep_insight.min_rank_score", fallback="")
        if configured:
            try:
                return float(configured)
            except ValueError:
                pass
        return self.get_float("deep_insight.min_value_score", 6.0)

    @property
    def deep_insight_require_full_content(self) -> bool:
        """L3 是否要求原文全文"""
        val = self.get(option="deep_insight.require_full_content", fallback="true")
        return val.lower() == "true"

    @property
    def candidate_pool_config(self) -> Dict:
        """正文读取前的来源候选池和分类补采配置。"""
        return {
            "candidate_limit_per_source": self.get_int(
                "candidate_pool.max_candidates_per_source", 100
            ),
            "initial_scored_per_source": self.get_int(
                "candidate_pool.initial_scored_per_source", 50
            ),
            "refill_min_per_category": self.get_int(
                "candidate_pool.refill_min_per_category", 2
            ),
            "refill_max_per_category": self.get_int(
                "candidate_pool.refill_max_per_category", 10
            ),
            "min_scoring_content_chars": self.get_int(
                "candidate_pool.min_scoring_content_chars", 100
            ),
        }

    def processing_limits(
        self,
        from_date: str = None,
        to_date: str = None,
        collection_period: str = None,
    ) -> Dict:
        """Resolve per-run limits from an explicit or inferred collection period."""
        period = (collection_period or "auto").strip().lower()
        weekly_max_days = self.get_int("collection.weekly_max_days", 7)
        if period == "auto":
            period = self.get(option="collection.default_period", fallback="weekly").lower()
            if from_date and to_date:
                try:
                    start = datetime.fromisoformat(from_date).date()
                    end = datetime.fromisoformat(to_date).date()
                    if end >= start:
                        period = "weekly" if (end - start).days + 1 <= weekly_max_days else "monthly"
                except ValueError:
                    pass
        if period not in {"weekly", "monthly", "quarterly"}:
            raise ValueError("collection_period 仅支持 auto、weekly、monthly 或 quarterly")

        candidate_pool = dict(self.candidate_pool_config)
        l3_max_candidates = self.l3_selection_config["max_candidates_per_batch"]
        if period == "weekly":
            candidate_pool["candidate_limit_per_source"] = self.get_int(
                "candidate_pool.weekly_max_candidates_per_source", 60
            )
            candidate_pool["initial_scored_per_source"] = self.get_int(
                "candidate_pool.weekly_initial_scored_per_source", 30
            )
            l3_max_candidates = self.get_int(
                "l3_selection.weekly_max_candidates_per_batch", 40
            )
        return {
            "period": period,
            "candidate_pool": candidate_pool,
            "l3_max_candidates": l3_max_candidates,
        }

    @property
    def title_routing_config(self) -> Dict:
        """Lightweight semantic routing configuration for mixed sources."""
        return {
            "enabled": self.get(
                option="title_routing.enabled", fallback="true"
            ).lower() == "true",
            "batch_size": self.get_int("title_routing.batch_size", 20),
            "min_confidence": self.get_float("title_routing.min_confidence", 0.65),
            "max_tokens": self.get_int("title_routing.max_tokens", 4096),
        }

    @property
    def l3_selection_config(self) -> Dict:
        """L3 前置主题聚合和统一评分排序配置。"""
        return {
            "max_candidates_per_batch": self.get_int("l3_selection.max_candidates_per_batch", 50),
            "topic_similarity_threshold": self.get_float(
                "l3_selection.topic_similarity_threshold", 0.34
            ),
        }

    # === 日志配置 ===

    @property
    def log_config(self) -> Dict:
        """日志配置"""
        return {
            "app_log_path": self.get(option="logging.app_log.path", fallback="./logs/app.log"),
            "app_log_level": self.get(option="logging.app_log.level", fallback="INFO"),
            "app_log_retention": self.get_int("logging.app_log.retention_days", 30),
            "error_log_path": self.get(option="logging.error_log.path", fallback="./logs/error.log"),
            "error_log_retention": self.get_int("logging.error_log.retention_days", 90),
        }

    # === 存储路径 ===

    @property
    def data_dir(self) -> str:
        """本地数据目录"""
        return self.get(option="storage.data_dir", fallback="./data")

    @property
    def temp_retention_days(self) -> int:
        """临时文件保留天数"""
        return self.get_int("storage.temp_retention_days", 7)

    @property
    def browser_fallback_config(self) -> Dict:
        """普通 HTTP 采集失败时的 Headless Chromium 降级配置。"""
        executable_path = self.get(
            option="browser_fallback.executable_path",
            fallback="",
        ).strip() or os.environ.get("PLAYWRIGHT_BROWSER_EXECUTABLE_PATH", "").strip()
        return {
            "enabled": self.get(option="browser_fallback.enabled", fallback="false").lower() == "true",
            "timeout_seconds": self.get_int("browser_fallback.timeout_seconds", 45),
            "min_content_chars": self.get_int("browser_fallback.min_content_chars", 300),
            "executable_path": os.path.expandvars(executable_path),
        }

    @property
    def discovery_config(self) -> Dict:
        """覆盖不足时优先站内发现，外部搜索 API 仅作为可选补充。"""
        key_env = self.get(
            option="discovery.search.api_key_env",
            fallback=self.get(option="discovery.api_key_env", fallback="SEARCH_API_KEY"),
        )
        search_endpoint = self.get(
            option="discovery.search.endpoint",
            fallback=self.get(option="discovery.search_endpoint", fallback=""),
        )
        mode = self.get(option="discovery.mode", fallback="site").strip().lower()
        if mode not in ("site", "search", "hybrid"):
            mode = "site"
        return {
            "enabled": self.get(option="discovery.enabled", fallback="false").lower() == "true",
            "mode": mode,
            "max_sources_per_run": self.get_int("discovery.max_sources_per_run", 9),
            "max_pages_per_source": self.get_int("discovery.max_pages_per_source", 3),
            "max_urls_per_source": self.get_int("discovery.max_urls_per_source", 12),
            "crawl_depth": self.get_int("discovery.crawl_depth", 2),
            "max_sitemaps_per_source": self.get_int("discovery.max_sitemaps_per_source", 5),
            "recency_days": self.get_int("discovery.recency_days", 30),
            "request_interval_seconds": self.get_float("discovery.request_interval_seconds", 0.2),
            "search_enabled": self.get(
                option="discovery.search.enabled",
                fallback="false",
            ).lower() == "true",
            "search_endpoint": search_endpoint,
            "query_param": self.get(
                option="discovery.search.query_param",
                fallback=self.get(option="discovery.query_param", fallback="q"),
            ),
            "count_param": self.get(
                option="discovery.search.count_param",
                fallback=self.get(option="discovery.count_param", fallback="count"),
            ),
            "api_key_header": self.get(
                option="discovery.search.api_key_header",
                fallback=self.get(
                    option="discovery.api_key_header",
                    fallback="Ocp-Apim-Subscription-Key",
                ),
            ),
            "api_key": os.environ.get(key_env, ""),
            "timeout_seconds": self.get_int("discovery.timeout_seconds", 20),
            "max_queries_per_run": self.get_int("discovery.search.max_queries_per_run", 6),
            "max_results_per_query": self.get_int("discovery.search.max_results_per_query", 8),
            "min_articles_per_category": self.get_int("discovery.min_articles_per_category", 2),
            "max_primary_source_ratio": self.get_float("discovery.max_primary_source_ratio", 0.4),
            "browser_source_options": {
                "_browser_fallback_enabled": str(self.browser_fallback_config["enabled"]).lower(),
                "_browser_timeout_seconds": str(self.browser_fallback_config["timeout_seconds"]),
                "_browser_min_content_chars": str(self.browser_fallback_config["min_content_chars"]),
                "_browser_executable_path": self.browser_fallback_config["executable_path"],
            },
        }

    # === 安全白名单 ===

    @property
    def allowed_domains(self) -> List[str]:
        """出站允许域名白名单"""
        raw = self.get(option="security.allowed_domains")
        return [d.strip() for d in raw.split(",") if d.strip()]

    # === 代理配置 ===

    @property
    def proxy_url(self) -> Optional[str]:
        """出站 HTTP 代理地址，公司网络访问外网时必需，返回 None 表示不走代理"""
        if self.get(option="proxy.enabled", fallback="false").lower() != "true":
            return None
        return self.get(option="proxy.url", fallback="") or None
