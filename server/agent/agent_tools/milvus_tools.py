"""
Milvus 工具集 —— 面试题库检索 + 管理员 Milvus 管理

面试工具的 collection/partition 通过 contextvars 实现协程级隔离，
多个并发 InterviewAgent 互不干扰。
"""

import json
import logging
from contextvars import ContextVar

from langchain_core.tools import tool
from pymilvus import AnnSearchRequest, RRFRanker
from server.config import milvus_client, embedding, settings

_log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Interview 工具：search_question_bank
# ═══════════════════════════════════════════════════════════

_collection: ContextVar[str] = ContextVar("interview_collection", default="")
_partition_expr: ContextVar[str | None] = ContextVar("interview_partition", default=None)


def configure(collection_name: str, partition: str | None = None):
    """InterviewAgent 初始化时调用，注入当前协程的题库集合名和分区过滤"""
    _collection.set(collection_name)
    _partition_expr.set(
        f'question_bank_partition == "{partition}"' if partition else None
    )


@tool
def search_question_bank(query: str, question_type: str = "technical", top_k: int = 5) -> str:
    """从题库中检索面试题目。当需要出技术题时调用此工具。

    Args:
        query: 检索关键词（如 "Python并发" "MySQL索引"）
        question_type: 题型 self_intro/project/technical/behavioral/qa
        top_k: 返回题目数

    Returns:
        JSON格式的题目列表，含题目、参考答案、评分标准、难度
    """
    collection = _collection.get()
    if not collection:
        return '{"error": "题库尚未初始化，请联系管理员"}'

    try:
        _log.info("检索题库：%s，关键词：%s", collection, query)
        resp = embedding.embeddings.create(
            model=settings.embedding_model,
            input=query,
            dimensions=1024,
        )
        vector = resp.data[0].embedding

        result = milvus_client.hybrid_search(
            collection_name=collection,
            reqs=[
                AnnSearchRequest(data=[vector], anns_field="vector",
                                 param={"metric_type": "COSINE"}, limit=top_k),
                AnnSearchRequest(data=[query], anns_field="sparse",
                                 param={"metric_type": "BM25"}, limit=top_k),
            ],
            ranker=RRFRanker(k=100),
            limit=top_k,
            output_fields=["question", "answer", "scoring_criteria", "difficulty", "question_bank_partition"],
            filter=_partition_expr.get(),
        )

        hits = result[0] if result else []

        if not hits:
            return json.dumps(
                {"count": 0, "message": f"未检索到与「{query}」相关的题目"},
                ensure_ascii=False,
            )

        results = []
        for h in hits:
            entity = h.get("entity", {})
            results.append({
                "question": entity.get("question", ""),
                "answer": entity.get("answer", ""),
                "scoring_criteria": entity.get("scoring_criteria", ""),
                "difficulty": entity.get("difficulty", 3),
                "score": round(h.get("distance", 0), 4),
            })
        _log.info("检索结果：%s", results)
        return json.dumps({"count": len(results), "results": results}, ensure_ascii=False)
    except Exception as e:
        _log.warning("题库检索失败: %s", e)
        return json.dumps(
            {"error": f"题库检索失败: {str(e)}"},
            ensure_ascii=False,
        )


# ═══════════════════════════════════════════════════════════
# Admin 工具：Milvus 管理
# ═══════════════════════════════════════════════════════════

@tool
def search_milvus(collection_name: str, query: str, top_k: int = 10) -> str:
    """在指定的 Milvus 集合中进行混合检索（密集向量 + BM25 → RRF 融合）。

    Args:
        collection_name: Milvus 集合名称
        query: 检索关键词
        top_k: 返回结果数

    Returns:
        JSON 格式的检索结果列表
    """
    from server.dao.milvus_db import MilvusDataBase
    try:
        mdb = MilvusDataBase(collection_name)
        hits = mdb._rrf_search(query=query, top_k=top_k, output_fields=["*"])
        results = []
        for h in hits:
            entity = h.get("entity", {})
            results.append({
                "id": h.get("id", ""),
                "distance": round(h.get("distance", 0), 4),
                "fields": {k: v for k, v in entity.items()},
            })
        return json.dumps({"count": len(results), "results": results}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def list_milvus_collections() -> str:
    """列出所有 Milvus 集合名称。

    Returns:
        JSON 格式的集合名称列表
    """
    try:
        cols = milvus_client.list_collections()
        return json.dumps({"collections": cols}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def describe_milvus_collection(collection_name: str) -> str:
    """查看指定 Milvus 集合的 schema 结构。

    Args:
        collection_name: Milvus 集合名称

    Returns:
        JSON 格式的字段定义、索引信息等
    """
    try:
        desc = milvus_client.describe_collection(collection_name)
        fields = []
        for f in desc.get("fields", []):
            fields.append({
                "name": f.get("name"),
                "type": str(f.get("type")),
                "is_primary": f.get("is_primary", False),
                "description": f.get("description", ""),
            })
        return json.dumps({
            "collection_name": desc.get("collection_name"),
            "description": desc.get("description", ""),
            "fields": fields,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
