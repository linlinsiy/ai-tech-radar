"""
AWS 侧 Prompt 加载模块

从 config/prompts/ 目录加载 L2/L3 Prompt 模板。
每个 .properties 文件包含 version / model / system / prompt 字段，
每次修改 prompt 后更新 version，调用时记录到分析结果的 prompt_version。
"""
import os
from typing import Dict, Optional
from configparser import ConfigParser

from logging_config import get_logger

logger = get_logger("llm.prompts")


class PromptRegistry:
    """
    Prompt 模板注册表

    类变量：
        _prompts: 已加载的 prompt 字典，key 为文件名（如 l2_summary）
        _config_dir: prompt 文件目录
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化 Prompt 注册表

        入参：
            config_dir: prompt 目录，默认 ./config/prompts
        """
        if config_dir is None:
            base = os.environ.get("AI_RADAR_CONFIG_DIR", "./config")
            config_dir = os.path.join(base, "prompts")
        self._config_dir = config_dir
        self._prompts: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        """加载目录中所有 .properties 文件（手动解析 key=value，兼容带 \ 续行符的多行值）"""
        if not os.path.isdir(self._config_dir):
            logger.warning("Prompt 目录不存在: %s", self._config_dir)
            return
        for fname in os.listdir(self._config_dir):
            if not fname.endswith(".properties"):
                continue
            path = os.path.join(self._config_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw_lines = fh.readlines()

                # 手动解析 key=value，处理 \ 续行符
                props = {}
                current_key = None
                current_value_parts = []

                for line in raw_lines:
                    stripped = line.strip()
                    # 跳过空行、注释、节头
                    if not stripped or stripped.startswith("#") or stripped.startswith("["):
                        continue

                    if current_key is None:
                        # 新 key=value 行
                        if "=" in stripped:
                            key, _, value = stripped.partition("=")
                            current_key = key.strip()
                            if value.endswith("\\"):
                                current_value_parts.append(value[:-1])
                            else:
                                props[current_key] = value
                                current_key = None
                    else:
                        # 续行
                        if stripped.endswith("\\"):
                            current_value_parts.append(stripped[:-1])
                        else:
                            current_value_parts.append(stripped)
                            props[current_key] = "".join(current_value_parts)
                            current_key = None
                            current_value_parts = []

                # 处理最后一条未闭合的续行
                if current_key is not None:
                    props[current_key] = "".join(current_value_parts)

                # 将值中的 \n 转义序列还原为实际换行符
                for k in list(props.keys()):
                    props[k] = props[k].replace("\\n", "\n")

                prompt_name = fname.replace(".properties", "")
                self._prompts[prompt_name] = {
                    "version": props.get("version", "unknown"),
                    "system": props.get("system", ""),
                    "prompt": props.get("prompt", ""),
                    "categories": props.get("categories", ""),
                    "model": props.get("model", ""),
                }
                logger.info(
                    "加载 Prompt: %s (version=%s)", prompt_name,
                    self._prompts[prompt_name]["version"]
                )
            except Exception as e:
                logger.error("加载 Prompt 失败: %s, %s", fname, str(e))
    def get(self, name: str) -> Optional[Dict]:
        """
        获取指定 prompt 模板

        入参：
            name: prompt 名称，如 l2_summary
        出参：prompt 字典 {version, system, prompt, categories, model}，不存在返回 None
        """
        return self._prompts.get(name)

    def render(
        self, name: str, **kwargs
    ) -> tuple:
        """
        渲染 prompt 模板

        入参：
            name: prompt 名称
            **kwargs: 模板占位符替换映射，如 title="xxx", summary="yyy"
        出参：(system_prompt, user_prompt, version, model_name)
              模板不存在时返回 ("", "", "", "")
        """
        tmpl = self.get(name)
        if not tmpl:
            logger.error("Prompt 模板不存在: %s", name)
            return "", "", "", ""

        system = tmpl["system"]
        user = tmpl["prompt"].format(**kwargs)
        return system, user, tmpl["version"], tmpl["model"]
