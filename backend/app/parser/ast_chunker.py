"""
AST-based code chunker using Tree-Sitter.

Strategy:
1. Detect language from file extension.
2. Parse the file into an AST via tree-sitter-languages.
3. Walk the AST and extract discrete top-level nodes:
   function_definition, class_definition, interface_declaration,
   method_definition, arrow_function (when assigned to a variable).
4. Prepend file-level import statements to every chunk for context.
5. Fall back to LangChain's RecursiveCharacterTextSplitter for
   unsupported or non-code files.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

import structlog

from app.core.config import settings
from app.models.schemas import ChunkMetadata, NodeType

log = structlog.get_logger(__name__)

# ── Language / extension mappings ─────────────────────────────────────────────
EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".cs": "c_sharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "bash",
    ".html": "html",
    ".css": "css",
}

# Node types to extract per language (Tree-Sitter grammar node names)
EXTRACT_NODE_TYPES: dict[str, list[str]] = {
    "python": [
        "function_definition",
        "async_function_definition",
        "class_definition",
        "decorated_definition",
    ],
    "javascript": [
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "lexical_declaration",      # const fn = () => {}
        "expression_statement",     # fn = function() {}
    ],
    "typescript": [
        "function_declaration",
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "lexical_declaration",
        "enum_declaration",
    ],
    "tsx": [
        "function_declaration",
        "class_declaration",
        "interface_declaration",
        "lexical_declaration",
        "type_alias_declaration",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
    "java": [
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "constructor_declaration",
    ],
    "rust": [
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
    ],
}

# Import node types per language (to build the context header)
IMPORT_NODE_TYPES: dict[str, list[str]] = {
    "python": ["import_statement", "import_from_statement"],
    "javascript": ["import_statement", "import_declaration"],
    "typescript": ["import_statement", "import_declaration"],
    "tsx": ["import_statement", "import_declaration"],
    "go": ["import_declaration"],
    "java": ["import_declaration"],
    "rust": ["use_declaration"],
}


# ── Helper: lazy-load tree-sitter language ────────────────────────────────────
def _get_parser(language: str):
    """Return a tree-sitter Parser for the given language, or None."""
    try:
        from tree_sitter_languages import get_parser  # type: ignore
        return get_parser(language)
    except Exception as exc:
        log.debug("tree_sitter.unavailable", language=language, error=str(exc))
        return None


# ── Helper: extract node text ─────────────────────────────────────────────────
def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte: node.end_byte].decode("utf-8", errors="replace")


def _node_name(node, source_bytes: bytes, language: str) -> Optional[str]:
    """Best-effort extraction of the function/class name from a node."""
    # Most grammars put the identifier as the first 'name' or 'identifier' child
    for child in node.children:
        if child.type in ("identifier", "name", "type_identifier", "field_identifier"):
            return _node_text(child, source_bytes)
    return None


def _node_type_from_grammar(grammar_type: str) -> NodeType:
    mapping = {
        "function_definition": NodeType.FUNCTION,
        "async_function_definition": NodeType.FUNCTION,
        "function_declaration": NodeType.FUNCTION,
        "generator_function_declaration": NodeType.FUNCTION,
        "function_item": NodeType.FUNCTION,
        "function_expression": NodeType.FUNCTION,
        "method_declaration": NodeType.METHOD,
        "method_definition": NodeType.METHOD,
        "class_definition": NodeType.CLASS,
        "class_declaration": NodeType.CLASS,
        "impl_item": NodeType.CLASS,
        "struct_item": NodeType.CLASS,
        "interface_declaration": NodeType.INTERFACE,
        "trait_item": NodeType.INTERFACE,
        "type_alias_declaration": NodeType.UNKNOWN,
        "decorated_definition": NodeType.FUNCTION,   # may wrap class too
    }
    return mapping.get(grammar_type, NodeType.UNKNOWN)


# ── Import extraction ─────────────────────────────────────────────────────────
def _extract_imports(root_node, source_bytes: bytes, language: str) -> str:
    """Collect all top-level import lines as a single header string."""
    import_types = IMPORT_NODE_TYPES.get(language, [])
    if not import_types:
        return ""
    lines: list[str] = []
    for node in root_node.children:
        if node.type in import_types:
            lines.append(_node_text(node, source_bytes))
    return "\n".join(lines)


# ── Fallback: RecursiveCharacterTextSplitter ──────────────────────────────────
def _fallback_chunks(
    content: str,
    file_path: str,
    language: str,
    repo_id: str,
) -> List[ChunkMetadata]:
    """Use LangChain splitter when Tree-Sitter is unavailable or unsupported."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # lazy import

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
    )
    texts = splitter.split_text(content)
    chunks: list[ChunkMetadata] = []
    line_cursor = 1
    for text in texts[: settings.MAX_CHUNKS_PER_FILE]:
        line_count = text.count("\n") + 1
        chunks.append(
            ChunkMetadata(
                repo_id=repo_id,
                file_path=file_path,
                language=language,
                node_type=NodeType.MODULE,
                node_name=None,
                start_line=line_cursor,
                end_line=line_cursor + line_count - 1,
                code_snippet=text,
                import_context="",
            )
        )
        line_cursor += line_count
    return chunks


# ── Primary AST chunker ────────────────────────────────────────────────────────
def chunk_file(
    content: str,
    file_path: str,
    repo_id: str,
) -> List[ChunkMetadata]:
    """
    Parse *content* (source code of a single file) into semantically
    meaningful chunks. Returns an empty list for binary/empty files.
    """
    if not content.strip():
        return []

    ext = Path(file_path).suffix.lower()
    language = EXT_TO_LANG.get(ext, "")

    # ── Tree-Sitter path ──────────────────────────────────────────────────────
    if language and language in EXTRACT_NODE_TYPES:
        parser = _get_parser(language)
        if parser:
            source_bytes = content.encode("utf-8")
            tree = parser.parse(source_bytes)
            root = tree.root_node

            import_ctx = _extract_imports(root, source_bytes, language)
            target_types = set(EXTRACT_NODE_TYPES[language])

            chunks: list[ChunkMetadata] = []
            _walk_ast(
                root, source_bytes, target_types, import_ctx,
                file_path, language, repo_id, chunks,
            )

            if chunks:
                log.debug(
                    "ast_chunker.done",
                    file=file_path,
                    language=language,
                    chunks=len(chunks),
                )
                return chunks[: settings.MAX_CHUNKS_PER_FILE]

    # ── Fallback ──────────────────────────────────────────────────────────────
    log.debug("ast_chunker.fallback", file=file_path, ext=ext)
    return _fallback_chunks(content, file_path, language or ext, repo_id)


def _walk_ast(
    node,
    source_bytes: bytes,
    target_types: set,
    import_ctx: str,
    file_path: str,
    language: str,
    repo_id: str,
    out: list,
    depth: int = 0,
) -> None:
    """Recursively walk the AST collecting target node types."""
    if node.type in target_types:
        snippet = _node_text(node, source_bytes)
        start_line = node.start_point[0] + 1   # tree-sitter is 0-indexed
        end_line = node.end_point[0] + 1
        out.append(
            ChunkMetadata(
                repo_id=repo_id,
                file_path=file_path,
                language=language,
                node_type=_node_type_from_grammar(node.type),
                node_name=_node_name(node, source_bytes, language),
                start_line=start_line,
                end_line=end_line,
                code_snippet=snippet,
                import_context=import_ctx,
            )
        )
        # Don't recurse inside already-captured nodes (avoids nested duplicates)
        return

    for child in node.children:
        _walk_ast(
            child, source_bytes, target_types, import_ctx,
            file_path, language, repo_id, out, depth + 1,
        )
