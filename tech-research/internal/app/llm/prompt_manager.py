"""Prompt 模板管理服务（内部侧）

使用 Jinja2 渲染 Prompt 模板，支持版本管理。
模板文件存放在 prompts/templates/ 目录下，.txt 格式。
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class PromptManager:
    """Prompt 模板管理器

    从 prompts/templates/ 加载 Jinja2 模板文件，
    支持变量渲染和版本管理。

    类变量：
        templates_dir: 模板文件目录
        versions_dir: 版本历史目录
        env: Jinja2 Environment 实例
    """

    def __init__(
        self,
        templates_dir: str = "prompts/templates",
        versions_dir: str = "prompts/versions",
    ) -> None:
        self.templates_dir = Path(templates_dir)
        self.versions_dir = Path(versions_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_template(self, template_name: str, **kwargs: str) -> str:
        """加载 Jinja2 模板并用给定变量渲染

        入参：
            template_name: 模板文件名（不含 .txt 扩展名）
            **kwargs: 模板变量键值对

        出参：
            渲染后的字符串

        异常：
            FileNotFoundError: 模板文件不存在
        """
        try:
            template = self.env.get_template(f"{template_name}.txt")
            return template.render(**kwargs)
        except TemplateNotFound:
            raise FileNotFoundError(f"模板未找到: {template_name}")

    def list_templates(self) -> list[str]:
        """列出所有可用的模板名称

        出参：
            模板名称列表（不含扩展名），按字母排序
        """
        if not self.templates_dir.is_dir():
            return []
        return sorted(
            p.stem for p in self.templates_dir.iterdir() if p.suffix == ".txt"
        )
