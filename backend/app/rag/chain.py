"""
LangChain RAG chain with streaming support.
Constructs the prompt from retrieved chunks and streams the LLM response
token-by-token via an async generator consumed by the SSE endpoint.

Updated for LangChain v1.x (LCEL-based, no deprecated LLMChain).
"""
from __future__ import annotations

from typing import AsyncIterator, List

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.models.schemas import SourceReference

log = structlog.get_logger(__name__)


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an expert software engineer and code analyst.
You are answering questions about a specific GitHub repository.

You will be given:
1. Code context: Relevant code snippets retrieved from the repository.
2. A question about the codebase.

Rules:
- Answer ONLY based on the provided code context.
- When referencing code, cite the file path and line numbers.
- If you cannot find the answer in the provided context, say so clearly.
- Format code examples using markdown code blocks with the appropriate language.
- Be concise, technical, and precise.
"""

_HUMAN_PROMPT = """Code Context:
{context}

Question: {question}

Answer:"""

# ── Prompt template (LCEL) ────────────────────────────────────────────────────
_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human", _HUMAN_PROMPT),
])


def _build_context(sources: List[SourceReference]) -> str:
    """Format retrieved source chunks into the LLM context string."""
    blocks: list[str] = []
    for src in sources:
        header = (
            f"### File: `{src.file_path}` "
            f"(lines {src.start_line}–{src.end_line})"
        )
        if src.node_name:
            header += f" | `{src.node_type.value}` `{src.node_name}`"
        blocks.append(f"{header}\n```{src.language}\n{src.snippet}\n```")
    return "\n\n---\n\n".join(blocks)


def _get_llm(streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENAI_API_KEY,
        streaming=streaming,
    )


# ── Non-streaming call ────────────────────────────────────────────────────────
async def generate_answer(
    question: str,
    sources: List[SourceReference],
) -> str:
    """Generate a complete answer (non-streaming). Returns full answer string."""
    context = _build_context(sources)
    llm = _get_llm(streaming=False)
    chain = _CHAT_PROMPT | llm
    result = await chain.ainvoke({"context": context, "question": question})
    # result is an AIMessage
    return result.content.strip()


# ── Streaming generator ───────────────────────────────────────────────────────
async def stream_answer(
    question: str,
    sources: List[SourceReference],
) -> AsyncIterator[str]:
    """
    Async generator that yields LLM response tokens one-by-one.
    The caller (SSE endpoint) iterates this and wraps each token in an SSE event.
    Uses LCEL astream() for native token-by-token streaming.
    """
    context = _build_context(sources)
    llm = _get_llm(streaming=True)
    chain = _CHAT_PROMPT | llm

    try:
        async for chunk in chain.astream({"context": context, "question": question}):
            # chunk is an AIMessageChunk; .content is the token string
            if chunk.content:
                yield chunk.content
    except Exception as exc:  # noqa: BLE001
        log.error("chain.stream_error", error=str(exc))
        raise
