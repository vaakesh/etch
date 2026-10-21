import re
from pathlib import Path

from rag.errors import CorpusError
from rag.types import Chunk

SEPARATOR = re.compile(r"(?m)^<!-- RAG_CHUNK -->\r?$")
IDENTIFIER = re.compile(r"(?m)^<!-- chunk_id: ([a-z0-9.-]+) -->\r?$")
MAX_CHUNK_CHARS = 1800


def split_markdown(markdown: str, source: str) -> list[Chunk]:
    """Split one Markdown document by explicit markers and validate its chunks."""
    chunks: list[Chunk] = []
    seen_ids = set()
    for block in SEPARATOR.split(markdown):
        block = block.strip()
        if not block:
            continue

        heading = block.splitlines()[0]
        matches = list(IDENTIFIER.finditer(block))
        if not heading.startswith("# ") or not heading[2:].strip() or len(matches) != 1:
            raise CorpusError(f"{source}: each chunk must have a title and exactly one chunk_id.")
        match = matches[0]
        chunk_id = match[1]
        if chunk_id in seen_ids:
            raise CorpusError(f"{source}: duplicate chunk_id {chunk_id}.")
        if len(block) > MAX_CHUNK_CHARS:
            raise CorpusError(f"{source}: chunk {chunk_id} exceeds {MAX_CHUNK_CHARS} characters.")

        text = (block[: match.start()] + block[match.end() :]).strip()
        if not "\n".join(text.splitlines()[1:]).strip():
            raise CorpusError(f"{source}: chunk {chunk_id} has no instruction text.")
        seen_ids.add(chunk_id)
        chunks.append(Chunk(chunk_id, heading[2:].strip(), text, source))

    if not chunks:
        raise CorpusError(f"{source}: document is empty.")
    return chunks


def load_chunks(folder: Path) -> list[Chunk]:
    """Read Markdown files from a folder and enforce unique IDs across the corpus."""
    folder = folder.resolve()
    paths = sorted(folder.glob("*.md"))
    if not paths:
        raise CorpusError(f"No Markdown documents found in {folder}.")

    chunks = []
    seen_ids = set()
    for path in paths:
        source = path.relative_to(folder.parent.parent).as_posix()
        try:
            markdown = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CorpusError(f"Failed to read {source}: {exc}") from exc
        for chunk in split_markdown(markdown, source):
            if chunk.chunk_id in seen_ids:
                raise CorpusError(f"{source}: duplicate chunk_id {chunk.chunk_id}.")
            seen_ids.add(chunk.chunk_id)
            chunks.append(chunk)
    return chunks
