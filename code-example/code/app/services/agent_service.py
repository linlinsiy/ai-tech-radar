"""Agent服务核心逻辑

实现LLM与联网搜索的智能组合：
1. 通过LLM判断是否需要搜索
2. 条件执行WebSearch
3. 基于搜索结果生成答案
"""
import json
import os
import re
from typing import Dict, Any, AsyncGenerator, Optional, List

from talentsview import AsyncLLMClient, AsyncWebSearch

from langfuse import get_client, observe

from app.utils.logger import get_logger
from app.utils.prompts import (
    build_search_decision_prompt,
    build_answer_with_context_prompt,
    build_direct_answer_prompt
)

logger = get_logger(__name__)
langfuse = get_client()  # Langfuse 单例客户端


class AgentServiceError(Exception):
    """Agent服务异常"""
    def __init__(self, message: str, error_code: str = "SERVICE_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AgentService:
    """Agent服务类
    
    提供智能对话能力，自动判断是否需要联网搜索
    使用 Langfuse context manager 确保单一 trace 嵌套结构
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        search_count: Optional[int] = None
    ):
        """初始化Agent服务
        
        Args:
            model: 模型名称，默认从环境变量读取
            temperature: 采样温度，默认从环境变量读取
            search_count: 搜索结果数量，默认从环境变量读取
        """
        # 从环境变量获取配置，支持默认值
        self.model = model or os.getenv("DEFAULT_MODEL", "local-qwen3-235b-nothink-moe")
        self.temperature = temperature or float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
        self.search_count = search_count or int(os.getenv("DEFAULT_SEARCH_COUNT", "5"))
        
        # 初始化SDK客户端
        try:
            self.llm_client = AsyncLLMClient(model=self.model)
            self.search_client = AsyncWebSearch(timeout=60)
            logger.info(f"Agent服务初始化成功，模型: {self.model}, 温度: {self.temperature}")
        except Exception as e:
            logger.error(f"Agent服务初始化失败: {str(e)}")
            if "803" in str(e):
                raise AgentServiceError("应用ID或智能体ID配置有误，请检查后重试", "CONFIG_ERROR")
            raise AgentServiceError(f"服务初始化失败: {str(e)}", "INIT_ERROR")
    
    async def chat(self, message: str) -> Dict[str, Any]:
        """执行Agent对话（非流式）
        
        Args:
            message: 用户输入的问题
            
        Returns:
            包含answer、used_search、search_results、model字段的字典
            
        Raises:
            AgentServiceError: 服务调用失败或配置错误
        """
        logger.info(f"收到用户问题: {message[:50]}...")
        
        # root trace，子方法的 @observe 自动嵌套
        with langfuse.start_as_current_observation(
            name="agent-chat",
            as_type="span",
            input={"message": message, "model": self.model}
        ) as trace:
            try:
                # 阶段1：判断是否需要搜索
                decision = await self._should_search(message)
                logger.info(f"搜索决策: need_search={decision['need_search']}, reason={decision.get('reason', '')}")
                
                search_results_text = None
                search_results_list = None
                
                # 阶段2：条件执行搜索
                if decision["need_search"]:
                    search_query = decision.get("search_query", message)
                    logger.info(f"开始搜索: {search_query}")
                    search_results_text, search_results_list = await self._execute_search(search_query)
                    logger.info(f"搜索完成，获得 {len(search_results_list) if search_results_list else 0} 条结果")
                
                # 阶段3：生成最终答案
                answer = await self._generate_answer(message, search_results_text, decision["need_search"])
                logger.info(f"回答生成完成，长度: {len(answer)} 字符")
                
                result = {
                    "answer": answer,
                    "used_search": decision["need_search"],
                    "search_results": search_results_list if decision["need_search"] else None,
                    "model": self.model
                }
                
                trace.update(output=result)
                return result
                
            except AgentServiceError:
                trace.update(level="ERROR")
                raise
            except Exception as e:
                trace.update(level="ERROR", status_message=str(e))
                logger.error(f"Agent对话失败: {str(e)}", exc_info=True)
                if "803" in str(e):
                    raise AgentServiceError("应用ID或智能体ID配置有误，请检查后重试", "CONFIG_ERROR")
                elif "timeout" in str(e).lower():
                    raise AgentServiceError("网络连接超时，请稍后重试", "TIMEOUT_ERROR")
                else:
                    raise AgentServiceError(f"服务调用失败: {str(e)}", "SERVICE_ERROR")
    
    async def chat_stream(self, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """执行Agent对话（流式）
        
        Args:
            message: 用户输入的问题
            
        Yields:
            流式数据块，包含delta、done、used_search字段
            
        Raises:
            AgentServiceError: 服务调用失败或配置错误
        """
        logger.info(f"收到用户问题(流式): {message[:50]}...")
        
        # root trace
        with langfuse.start_as_current_observation(
            name="agent-chat-stream",
            as_type="span",
            input={"message": message, "model": self.model, "stream": True}
        ) as trace:
            try:
                # 阶段1：判断是否需要搜索
                decision = await self._should_search(message)
                logger.info(f"搜索决策: need_search={decision['need_search']}")
                
                search_results_text = None
                
                # 阶段2：条件执行搜索
                if decision["need_search"]:
                    search_query = decision.get("search_query", message)
                    logger.info(f"开始搜索: {search_query}")
                    search_results_text, _ = await self._execute_search(search_query)
                    logger.info("搜索完成")
                
                # 阶段3：流式生成答案
                logger.info("开始流式生成答案")
                async for chunk in self._generate_answer_stream(message, search_results_text, decision["need_search"]):
                    yield chunk
                
                # 最后发送done信号
                yield {
                    "delta": "",
                    "done": True,
                    "used_search": decision["need_search"]
                }
                
                trace.update(output={"used_search": decision["need_search"], "status": "completed"})
                logger.info("流式生成完成")
                
            except AgentServiceError:
                trace.update(level="ERROR")
                raise
            except Exception as e:
                trace.update(level="ERROR", status_message=str(e))
                logger.error(f"Agent流式对话失败: {str(e)}", exc_info=True)
                if "803" in str(e):
                    raise AgentServiceError("应用ID或智能体ID配置有误，请检查后重试", "CONFIG_ERROR")
                elif "timeout" in str(e).lower():
                    raise AgentServiceError("网络连接超时，请稍后重试", "TIMEOUT_ERROR")
                else:
                    raise AgentServiceError(f"服务调用失败: {str(e)}", "SERVICE_ERROR")
    
    @observe(name="search-decision", as_type="generation")
    async def _should_search(self, message: str) -> Dict[str, Any]:
        """判断是否需要搜索
            
        Args:
            message: 用户问题
                
        Returns:
            包含need_search、search_query、reason字段的字典
        """
        prompt = build_search_decision_prompt(message)
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 使用较低温度保证稳定性
                stream=False
            )
            
            content = response.choices[0].message.content
            logger.debug(f"搜索决策原始响应: {content}")
            
            # 解析JSON响应
            decision = self._parse_json_response(content)
            
            # 验证必需字段
            if "need_search" not in decision:
                logger.warning("LLM未返回need_search字段，默认不搜索")
                return {"need_search": False, "reason": "解析失败"}
            
            return decision
            
        except Exception as e:
            logger.error(f"搜索决策失败: {str(e)}")
            # 决策失败时默认不搜索
            return {"need_search": False, "reason": f"决策失败: {str(e)}"}
    
    @observe(name="web-search")
    async def _execute_search(self, query: str) -> tuple[Optional[str], Optional[List[Dict]]]:
        """执行联网搜索
        
        Args:
            query: 搜索关键词
            
        Returns:
            (清洗后的文本, 原始搜索结果列表)
        """
        try:
            # 获取清洗后的文本（LLM友好格式）
            clean_text = await self.search_client.search(
                query=query,
                count=self.search_count,
                clean=True
            )
            
            # 同时获取结构化结果用于返回
            raw_results = await self.search_client.search(
                query=query,
                count=self.search_count,
                clean=False
            )
            
            # 转换为字典列表
            results_list = []
            if raw_results:
                for item in raw_results:
                    results_list.append({
                        "title": item.title,
                        "url": item.url if hasattr(item, 'url') else "",
                        "snippet": item.snippet,
                        "auth_info_level": item.auth_info_level if hasattr(item, 'auth_info_level') else 0
                    })
            
            return clean_text, results_list
            
        except Exception as e:
            logger.error(f"搜索执行失败: {str(e)}")
            if "500" in str(e) or "INTERNAL" in str(e).upper():
                raise AgentServiceError("搜索服务繁忙，请稍后重试", "SEARCH_ERROR")
            raise AgentServiceError(f"搜索失败: {str(e)}", "SEARCH_ERROR")
    
    @observe(name="answer-generation", as_type="generation")
    async def _generate_answer(
        self,
        message: str,
        search_results: Optional[str],
        used_search: bool
    ) -> str:
        """生成最终答案（非流式）
        
        Args:
            message: 用户问题
            search_results: 搜索结果文本（如果有）
            used_search: 是否使用了搜索
            
        Returns:
            生成的答案文本
        """
        # 构造Prompt
        if used_search and search_results:
            prompt = build_answer_with_context_prompt(message, search_results)
        else:
            prompt = build_direct_answer_prompt(message)
        
        logger.debug(f"生成答案Prompt长度: {len(prompt)}")
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                stream=False
            )
            
            answer = response.choices[0].message.content
            return answer
            
        except Exception as e:
            logger.error(f"答案生成失败: {str(e)}")
            raise
    
    async def _generate_answer_stream(
        self,
        message: str,
        search_results: Optional[str],
        used_search: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """生成最终答案（流式）
        
        Args:
            message: 用户问题
            search_results: 搜索结果文本（如果有）
            used_search: 是否使用了搜索
            
        Yields:
            包含delta和done字段的字典
        """
        # 构造Prompt
        if used_search and search_results:
            prompt = build_answer_with_context_prompt(message, search_results)
        else:
            prompt = build_direct_answer_prompt(message)
        
        logger.debug(f"流式生成答案Prompt长度: {len(prompt)}")
        
        try:
            stream = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {
                        "delta": chunk.choices[0].delta.content,
                        "done": False
                    }
            
        except Exception as e:
            logger.error(f"流式答案生成失败: {str(e)}")
            raise
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应
        
        Args:
            content: LLM返回的文本内容
            
        Returns:
            解析后的字典
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # 尝试提取{}包裹的内容
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"无法解析JSON响应: {content}")
            return {"need_search": False, "reason": "JSON解析失败"}
