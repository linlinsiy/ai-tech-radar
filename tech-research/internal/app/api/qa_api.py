"""
内部侧 - RAG 问答接口

POST /api/v1/qa/ask

接收内部用户/系统的问题，调用 EIPLite 内置 RAG 问答，
返回带来源引用的答案。支持标签过滤缩小召回范围。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from config import InternalConfig
from kb.kb_client import create_kb_client, KBError

logger = logging.getLogger("qa_api")

def verify_qa_token(authorization: str = Header(None)) -> bool:
    """
    校验 QA 接口 Bearer token
    
    入参：
        authorization: HTTP Authorization 请求头
    出参：
        True 放行
    
    若 QA_API_TOKEN 未配置则跳过校验；否则校验 Bearer token 是否匹配。
    """
    token = InternalConfig.get_instance().qa_config.get("token")
    if not token:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if authorization[7:] != token:
        raise HTTPException(status_code=401, detail="Invalid Bearer token")
    return True


router = APIRouter(dependencies=[Depends(verify_qa_token)])

class TagFilter(BaseModel):
    """标签过滤条件，对应 EIPLite 标签 Schema 中参与过滤的字段"""
    name: str = Field(..., description="标签名，如 category / kb_type / source_name")
    value: str = Field(..., description="标签值，如 推理优化 / article_summary / AWS ML Blog")


class QARequest(BaseModel):
    """RAG 问答请求"""
    question: str = Field(..., description="用户问题")
    knowledge_base: str = Field("AI技术知识库", description="目标知识库名称")
    top_k: int = Field(5, ge=1, le=20, description="返回片段数")
    tag_filters: Optional[List[TagFilter]] = Field(None, description="标签过滤条件列表")


@router.post("/api/v1/qa/ask")
async def ask_question(body: QARequest):
    """
    RAG 问答接口

    调用 EIPLite 内置问答接口（检索 + 生成一体化），
    默认混合检索，支持 tag_filters 缩小召回范围。

    入参：
        body: QARequest，含问题、知识库名、top_k、可选标签过滤
    出参：
        {
            "code": 0, "message": "ok",
            "data": {
                "answer": str,
                "sources": [{"title": str, "url": str, "kb_file_id": str, "relevance_score": float}],
                "retrieval_method": str,
                "tokens_used": int,
            }
        }

    失败降级策略：
        - EIPLite 不可用 → 503
        - 检索返回空 → 200 + 提示信息
        - 请求超时 → 503
    """
    logger.info("RAG 问答请求: question=%s..., top_k=%d, filters=%s",
                 body.question[:60], body.top_k,
                 [(f.name, f.value) for f in (body.tag_filters or [])])

    # 构建 EIPLite 客户端
    cfg = InternalConfig.get_instance().kb_client_config
    if not cfg.get("base_url"):
        logger.warning("EIPLite 未配置 base_url，问答不可用")
        return {
            "code": 503,
            "message": "service_unavailable",
            "detail": "EIPLite 知识库平台未配置",
            "data": None,
        }

    try:
        client = create_kb_client()
        client.authenticate()
    except KBError as e:
        logger.error("EIPLite 认证失败: %s", e)
        raise HTTPException(status_code=503, detail={
            "code": 503,
            "message": "service_unavailable",
            "detail": f"EIPLite 认证失败: {e}",
        })

    # 转换 tag_filters 为 EIPLite 格式
    kb_client_filters = None
    if body.tag_filters:
        kb_client_filters = [{"name": f.name, "value": f.value} for f in body.tag_filters]

    try:
        result = client.ask(
            question=body.question,
            top_k=body.top_k,
            tag_filters=kb_client_filters,
            retrieval_method="hybrid",
        )
    except KBError as e:
        logger.error("EIPLite 问答失败: %s (status=%d)", e, e.status_code)
        raise HTTPException(status_code=503, detail={
            "code": 503,
            "message": "service_unavailable",
            "detail": f"EIPLite 问答调用失败: {e}",
        })
    finally:
        client.close()

    # 空结果降级
    if not result.get("answer") and not result.get("sources"):
        return {
            "code": 0,
            "message": "no_results",
            "data": {
                "answer": "未找到相关内容，建议调整问题或扩大检索范围。",
                "sources": [],
                "retrieval_method": "hybrid",
                "tokens_used": 0,
            },
        }

    # 部分降级：有来源但无 LLM 生成答案（内部大模型不可用）
    if not result.get("answer") and result.get("sources"):
        sources_text = "\n".join(
            f"- [{s.get('title', '未命名')}]({s.get('url', '')})" 
            for s in result["sources"]
        )
        return {
            "code": 0,
            "message": "ok",
            "data": {
                "answer": f"以下为检索到的相关内容，供参考：\n{sources_text}",
                "sources": result["sources"],
                "retrieval_method": result.get("retrieval_method", "hybrid"),
                "tokens_used": result.get("tokens_used", 0),
                "note": "仅返回检索片段，LLM 生成暂时不可用",
            },
        }

    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }
