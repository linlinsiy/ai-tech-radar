
"""
内部应用节点配置加载模

从环境变量和内部配置文件中读取 MySQL、EIPLite、内部大模型等配置。
机密信息通过 secrets/.env 环境变量注入
"""
import os
from configparser import ConfigParser
from typing import Dict


class InternalConfig:
    """
    内部应用节点全局配置管理器

    类变量：
        _instance: 单例实例
    """

    _instance = None

    def __init__(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._config_dir = os.environ.get(
            "AI_RADAR_INTERNAL_CONFIG_DIR",
            os.path.join(base, "config"),
        )
        self._config = ConfigParser(interpolation=None)
        self._load_config()
        self._load_env()

    @classmethod
    def get_instance(cls) -> "InternalConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self):
        """加载 config/config.properties"""
        props_path = os.path.join(self._config_dir, "config.properties")
        if os.path.exists(props_path):
            self._config.read(props_path, encoding="utf-8")

    def get(self, section: str = "DEFAULT", option: str = "", fallback: str = "") -> str:
        """读取配置文件中的单个配置项"""
        return self._config.get(section, option, fallback=fallback)

    def _load_env(self):
        """加载 secrets/.env 环境变量"""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base, "secrets", ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()

    # === MySQL 配置（已提供） ===

    @property
    def mysql_config(self) -> Dict[str, str]:
        """
        MySQL 连接配置

        出参：host/port/username/password/database/charset
        """
        return {
            "host": os.environ.get("MYSQL_HOST", "10.102.37.253"),
            "port": int(os.environ.get("MYSQL_PORT", "8880")),
            "username": os.environ.get("MYSQL_USERNAME", "ysdjg_user"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "ysdjg"),
            "charset": os.environ.get("MYSQL_CHARSET", "utf8mb4"),
        }

    # === TalentsView SDK 知识库配置 ===

    @property
    def talentsview_config(self) -> Dict[str, str]:
        """
        TalentsView SDK知识库平台配置

        出参：app_id/agent_id/workspace_id/kb_dataset_id

        """
        return {
            "app_id": os.environ.get("TALENTSVIEW_APP_ID", ""),
            "agent_id": os.environ.get("TALENTSVIEW_AGENT_ID", ""),
            "workspace_id": os.environ.get("TALENTSVIEW_WORKSPACE_ID", ""),
            "kb_dataset_id": os.environ.get("EIPLITE_KB_DATASET_ID", ""),
        }

    # === 内部大模型配置（待用户提供） ===

    @property
    def internal_llm_config(self) -> Dict[str, str]:
        """
        内部大模型配置（用于简报生成和 RAG 问答）

        出参：api_key/base_url/model

        """
        return {
            "api_key": os.environ.get("LLM_API_KEY", ""),
            "model": os.environ.get("LLM_MODEL", ""),
            "base_url": os.environ.get("LLM_BASE_URL", ""),
            "user_id": os.environ.get("LLM_USER_ID", "013148"),
            "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.01")),
            "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "4096")),
        }

    # === ������������ ===

    @property
    def server_config(self) -> Dict:
        """服务运行配置"""
        return {
            "host": os.environ.get("SERVER_HOST", "0.0.0.0"),
            "port": int(os.environ.get("SERVER_PORT", "9001")),
            "workers": int(os.environ.get("SERVER_WORKERS", "1")),
        }


    # === QA 问答接口鉴权配置 ===

    @property
    def qa_config(self) -> Dict[str, str]:
        """
        QA 问答接口鉴权配置

        出参：token（空字符串表示不校验）
        """
        return {
            "token": os.environ.get("QA_API_TOKEN", ""),
        }

    # === XXL-Job 调度平台配置 ===

    @property
    def scheduler_config(self) -> Dict[str, str]:
        """
        调度模式配置

        mode:
            xxljob  - 启动时注册 XXL-Job Executor
            crontab - 不注册 XXL-Job，由本机 crontab 调 HTTP 接口
            none    - 不启用调度器
        """
        mode = self.get(option="scheduler.mode", fallback="xxljob").strip().lower()
        if mode not in ("xxljob", "crontab", "none"):
            mode = "xxljob"
        return {
            "mode": mode,
            "cron_briefing": self.get(option="scheduler.cron.briefing", fallback="0 9 * * 1"),
            "briefing_type": self.get(option="scheduler.briefing_type", fallback="weekly"),
        }

    @property
    def xxl_config(self) -> Dict[str, str]:
        """
        XXL-Job Executor 配置（内部侧）

        出参：admin_url/app_name/access_token/executor_port/log_path
        """
        return {
            "admin_url": os.environ.get("XXL_ADMIN_URL", "http://168.64.38.162:8080/xxl-job-admin/api/"),
            "app_name": os.environ.get("XXL_APP_NAME", "ai-radar-internal-executor"),
            "access_token": os.environ.get("XXL_ACCESS_TOKEN", "kSaGFtaEcMXcrPBGkyWWkM78yNtMKmhT"),
            "executor_port": int(os.environ.get("XXL_EXECUTOR_PORT", "9998")),
            "log_path": os.environ.get("XXL_LOG_PATH", "./logs/xxl-job"),
        }

    @property
    def import_config(self) -> Dict:
        """受控导入配置"""
        return {
            "max_batch_articles": int(os.environ.get("IMPORT_MAX_ARTICLES", "500")),
            "request_timeout": int(os.environ.get("IMPORT_TIMEOUT_SECONDS", "30")),
        }

    @property
    def briefing_selection_config(self) -> Dict:
        """L4 选题数量、统一评分门槛及软配额。"""
        return {
            "target_weekly": self._config.getint("DEFAULT", "briefing.selection.target_weekly", fallback=8),
            "target_monthly": self._config.getint("DEFAULT", "briefing.selection.target_monthly", fallback=14),
            "target_quarterly": self._config.getint("DEFAULT", "briefing.selection.target_quarterly", fallback=18),
            "target_topic": self._config.getint("DEFAULT", "briefing.selection.target_topic", fallback=12),
            "min_rank_score": self._config.getfloat("DEFAULT", "briefing.selection.min_rank_score", fallback=6.5),
            "max_primary_source_ratio": self._config.getfloat("DEFAULT", "briefing.selection.max_primary_source_ratio", fallback=0.15),
            "max_category_ratio": self._config.getfloat("DEFAULT", "briefing.selection.max_category_ratio", fallback=0.35),
            "min_sources_for_balance": self._config.getint("DEFAULT", "briefing.selection.min_sources_for_balance", fallback=3),
            "min_categories_for_balance": self._config.getint("DEFAULT", "briefing.selection.min_categories_for_balance", fallback=2),
            "topic_similarity_threshold": self._config.getfloat("DEFAULT", "briefing.selection.topic_similarity_threshold", fallback=0.34),
            "max_articles_per_topic": self._config.getint("DEFAULT", "briefing.selection.max_articles_per_topic", fallback=3),
        }

    @property
    def briefing_prompt_config(self) -> Dict[str, str]:
        """读取内部侧固定格式简报 Prompt。"""
        path = os.path.join(self._config_dir, "prompts", "l5_briefing.properties")
        parser = ConfigParser(interpolation=None)
        if os.path.exists(path):
            parser.read(path, encoding="utf-8")
        section = "简报生成 Prompt"
        return {
            "version": parser.get(section, "version", fallback="unknown"),
            "categories": parser.get(section, "categories", fallback=""),
            "system": parser.get(section, "system", fallback=""),
            "intro_prompt": parser.get(section, "intro_prompt", fallback=""),
            "section_prompt": parser.get(section, "section_prompt", fallback=""),
        }

    @property
    def data_dir(self) -> str:
        return self.get(option="storage.data_dir", fallback="./data")
