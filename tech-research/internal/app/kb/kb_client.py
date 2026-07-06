"""????????????

?? TalentsView Python SDK ?????????
- upload_chunks(): ?? Markdown ??????
- query(): ???????? metadata_filter ?????

?? REST API????? TalentsView SDK?
SDK ?????? TALENTSVIEW_APP_ID / TALENTSVIEW_AGENT_ID ?????
"""
import os
import logging
from typing import Any, List, Dict, Optional

logger = logging.getLogger("kb")


def _load_talentsview_client():
    """
    Lazily load TalentsView SDK.

    The internal service can start and accept MySQL imports without the SDK.
    Knowledge-base upload/query will fail with a clear error if the optional
    package is not installed.
    """
    try:
        from talentsview import KnowledgeBaseClient
        return KnowledgeBaseClient
    except ImportError as e:
        raise KBError(
            "talentsview_import",
            "talentsview SDK is not installed. Install talentsview==1.2.2 "
            "to enable knowledge-base upload/query, or leave "
            "EIPLITE_KB_DATASET_ID empty to skip KB upload."
        ) from e


def _load_talentsview_filter_types():
    """Lazily load TalentsView metadata filter types."""
    try:
        from talentsview.platform.knowledge_bases.types import (
            MetadataFilter,
            FilterComparison,
            FilterComparator,
            FilterValue,
            FilterOperator,
        )
        return MetadataFilter, FilterComparison, FilterComparator, FilterValue, FilterOperator
    except ImportError as e:
        raise KBError(
            "talentsview_import",
            "talentsview SDK is not installed. Metadata filters require talentsview==1.2.2."
        ) from e


class KBError(Exception):
    """??????????????????"""

    def __init__(self, operation: str, message: str):
        super().__init__(f"[{operation}] {message}")
        self.operation = operation


class KBClient:
    """???????TalentsView SDK ???

    ?? upload_chunks() ? query()?????????????

    ????
        _client: TalentsView KnowledgeBaseClient ???????
        _dataset_id: ????? dataset_id

    ?????
        ?????? TALENTSVIEW_APP_ID / TALENTSVIEW_AGENT_ID / TALENTSVIEW_WORKSPACE_ID ?????
        ?????? authenticate()?
    """

    DEFAULT_CHUNK_SIZE = 2000

    def __init__(
        self,
        dataset_id: Optional[str] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        """?????????

        ???
            dataset_id: ????? ID????? KB_DATASET_ID ??????
            chunk_size: ?????????????? 2000
        """
        self._dataset_id = dataset_id or os.environ.get("EIPLITE_KB_DATASET_ID", "")
        self._chunk_size = chunk_size
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """??? SDK ?????????????"""
        if self._client is None:
            KnowledgeBaseClient = _load_talentsview_client()
            self._client = KnowledgeBaseClient()
            logger.info("KBClient initialized: dataset_id=%s", self._dataset_id)
        return self._client

    @property
    def dataset_id(self) -> str:
        return self._dataset_id

    # -------- ???? --------

    def upload_file(
        self,
        content: str,
        filename: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """?? Markdown ???????? chunk_size ???

        ???
            content: Markdown ????
            filename: ????? .md ???
            tags: ????????SDK ???? upload_chunks ????????
                  ????????? Web UI ????????????? SDK ??????

        ???
            ???????? ID ? document_id????? None

        ?????
            ???? / ???????????<= chunk_size?
            ????????????
        """
        if not self._dataset_id:
            raise KBError("upload_file", "KB_DATASET_ID ???")

        logger.info("KB upload: filename=%s, content_len=%d", filename, len(content))

        try:
            chunks = self._split_content(content)
            result = self.client.upload_chunks(
                filename=filename,
                chunks=chunks,
                dataset_id=self._dataset_id,
                # tags removed: SDK upload_chunks does not support tags param,
            )
            file_id = self._extract_file_id(result)
            if file_id:
                logger.info("KB upload success: file_id=%s, chunks=%d", file_id, len(chunks))
            else:
                logger.warning(
                    "KB upload: response missing file_id: document_id=%s failed_chunks=%s",
                    str(result.get("document_id", "")),
                    str(result.get("failed_chunks", ""))
                )
            return file_id or filename
        except Exception as e:
            msg = f"???? filename={filename}: {e}"
            logger.error(msg)
            raise KBError("upload_file", msg) from e

    def _split_content(self, content: str) -> List[str]:
        """???? chunk_size ????????????

        ???
            content: ??????

        ???
            ??????????????? chunk_size ??
        """
        if len(content) <= self._chunk_size:
            return [content]

        chunks = []
        paragraphs = content.split("\n\n")
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 <= self._chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                current = para

        if current:
            chunks.append(current)

        # ???????????????
        final = []
        for chunk in chunks:
            while len(chunk) > self._chunk_size:
                final.append(chunk[: self._chunk_size])
                chunk = chunk[self._chunk_size :]
            if chunk:
                final.append(chunk)

        return final

    @staticmethod
    def _extract_file_id(result) -> Optional[str]:
        """\u4ece upload_chunks \u54cd\u5e94\u4e2d\u63d0\u53d6 file_id / document_id

        \u5165\u53c2\uff1a
            result: SDK upload_chunks \u8fd4\u56de\u7ed3\u679c\uff08\u53ef\u80fd\u662f dict \u6216 SDK \u81ea\u5b9a\u4e49\u5bf9\u8c61\uff09

        \u51fa\u53c2\uff1a
            file_id \u6216 document_id \u5b57\u7b26\u4e32\uff0c\u65e0\u6cd5\u63d0\u53d6\u8fd4\u56de None
        """
        if isinstance(result, str):
            return result
        # \u4f18\u5148 try dict-like access\uff08\u542b SDK \u81ea\u5b9a\u4e49\u5bf9\u8c61\u652f\u6301 .get \u4f46\u4e0d\u662f dict \u7684\u60c5\u51b5\uff09
        try:
            doc_id = result.get("document_id")
            if doc_id:
                return doc_id
            file_id = result.get("file_id")
            if file_id:
                return file_id
            obj_id = result.get("id")
            if obj_id:
                return obj_id
            data = result.get("data")
            if isinstance(data, dict):
                return data.get("file_id") or data.get("document_id")
            # SDK actual response: data is list
            if isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if isinstance(first_item, dict):
                    return (first_item.get('document_id')
                            or first_item.get('file_id')
                            or first_item.get('id'))
        except (AttributeError, TypeError):
            pass
        # \u5c1d\u8bd5\u901a\u8fc7 dict() \u8f6c\u6362 SDK \u5bf9\u8c61
        try:
            d = dict(result)
            return d.get("document_id") or d.get("file_id") or d.get("id")
        except (ValueError, TypeError):
            pass
        return None

    # -------- ????? --------

    def query(
        self,
        keywords: str,
        top_k: int = 5,
        tag_filters: Optional[List[Dict[str, str]]] = None,
        retrieval_method: str = "hybrid",
    ) -> Dict:
        """????????????

        ???
            keywords: ????? / ??
            top_k: ???????? 5
            tag_filters: ?????? [{"name": "category", "value": "????"}, ...]
            retrieval_method: ?????hybrid / vector / fulltext???? hybrid

        ???
            {
                "answer": "",       # query() ????????????
                "sources": [{"title": str, "url": str, "kb_file_id": str, "relevance_score": float}],
                "retrieval_method": str,
                "tokens_used": 0,
            }
        """
        if not self._dataset_id:
            raise KBError("query", "KB_DATASET_ID ???")

        logger.info(
            "KB query: keywords=%s..., top_k=%d, method=%s, filters=%d",
            keywords[:60], top_k, retrieval_method, len(tag_filters or []),
        )

        try:
            # ?? metadata_filter
            md_filter = None
            if tag_filters:
                (
                    MetadataFilter,
                    FilterComparison,
                    FilterComparator,
                    FilterValue,
                    FilterOperator,
                ) = _load_talentsview_filter_types()
                expressions = [
                    FilterComparison(
                        field=f["name"],
                        comparator=FilterComparator.EQ,
                        value=FilterValue(string_value=f["value"]),
                    )
                    for f in tag_filters
                ]
                md_filter = MetadataFilter(
                    operator=FilterOperator.AND,
                    expressions=expressions,
                )

            result = self.client.query(
                keywords=keywords,
                dataset_ids=[self._dataset_id],
                top_k=top_k,
                metadata_filter=md_filter,
            )

            # ?? SDK ?????????
            sources = self._parse_sources(result)
            return {
                "answer": "",
                "sources": sources,
                "retrieval_method": retrieval_method,
                "tokens_used": 0,
            }
        except Exception as e:
            msg = f"???? keywords={keywords[:60]}: {e}"
            logger.error(msg)
            raise KBError("query", msg) from e

    @staticmethod
    def _parse_sources(result) -> List[Dict]:
        """? SDK query() ????????????? sources ??

        ???
            result: SDK query() ????

        ???
            [{"title": str, "url": str, "kb_file_id": str, "relevance_score": float}]
        """
        sources = []
        if isinstance(result, dict):
            items = result.get("data") or result.get("items") or result.get("chunks") or []
        elif isinstance(result, list):
            items = result
        else:
            return sources

        for item in items:
            if isinstance(item, dict):
                sources.append({
                    "title": item.get("title") or item.get("name") or item.get("filename", ""),
                    "url": item.get("url") or item.get("link", ""),
                    "kb_file_id": (
                        item.get("document_id")
                        or item.get("file_id")
                        or item.get("id")
                        or item.get("chunk_id", "")
                    ),
                    "relevance_score": float(item.get("score") or item.get("relevance_score") or 0),
                })
        return sources


# ----------------------------------------------------------------
# ???????????? KBClient
# ----------------------------------------------------------------


def create_kb_client() -> KBClient:
    """??????? KBClient ??

    ????????
        EIPLITE_KB_DATASET_ID: ??? dataset_id????

    ???
        KBClient ??
    """
    dataset_id = os.environ.get("EIPLITE_KB_DATASET_ID", "")
    if not dataset_id:
        logger.warning("EIPLITE_KB_DATASET_ID ????KBClient ??? dataset_id ??")
    return KBClient(dataset_id=dataset_id)
