from pathlib import Path
from unittest.mock import patch

import pytest

from rag.chunks import load_chunks, split_markdown
from rag.errors import CorpusError
from rag.types import Chunk


class TestSplitMarkdown:
    def test_keeps_heading_and_removes_identifier_from_embedding_text(self):
        markdown = "# Создать карточку\n<!-- chunk_id: etch.cards.create -->\n\nНажмите «Создать»."

        chunks = split_markdown(markdown, "content/ru/05-cards.md")

        assert chunks == [
            Chunk(
                chunk_id="etch.cards.create",
                title="Создать карточку",
                text="# Создать карточку\n\n\nНажмите «Создать».",
                source="content/ru/05-cards.md",
            )
        ]

    def test_splits_only_on_full_marker_lines_and_supports_crlf(self):
        markdown = (
            "# Карточки\r\n<!-- chunk_id: etch.cards.create -->\r\n\r\n"
            "## Раздел\r\n---\r\nТекст <!-- RAG_CHUNK --> остаётся.\r\n"
            "<!-- RAG_CHUNK -->\r\n"
            "# Колоды\r\n<!-- chunk_id: etch.decks.create -->\r\nНажмите кнопку."
        )

        chunks = split_markdown(markdown, "guide.md")

        assert [chunk.chunk_id for chunk in chunks] == ["etch.cards.create", "etch.decks.create"]
        assert "## Раздел\r\n---\r\nТекст <!-- RAG_CHUNK --> остаётся." in chunks[0].text

    @pytest.mark.parametrize(
        "markdown",
        [
            "",
            " \n ",
            "# Заголовок\nТекст без идентификатора.",
            "Текст\n<!-- chunk_id: etch.cards.create -->",
            "# \n<!-- chunk_id: etch.cards.create -->\nТекст.",
            "# Заголовок\n<!-- chunk_id: etch.cards.create -->",
            "# Заголовок\n<!-- chunk_id: etch.cards.create -->\n"
            "<!-- chunk_id: etch.cards.edit -->\nТекст.",
            "# Заголовок\n<!-- chunk_id: etch.cards.create -->\n" + "а" * 1800,
        ],
    )
    def test_rejects_invalid_or_empty_chunks(self, markdown):
        with pytest.raises(CorpusError):
            split_markdown(markdown, "guide.md")

    def test_rejects_duplicate_identifiers_within_one_document(self):
        block = "# Карточки\n<!-- chunk_id: etch.cards.create -->\nТекст."

        with pytest.raises(CorpusError, match="duplicate chunk_id etch.cards.create"):
            split_markdown(f"{block}\n<!-- RAG_CHUNK -->\n{block}", "guide.md")


class TestLoadChunks:
    def test_rejects_folder_without_documents(self):
        with patch.object(Path, "glob", return_value=[]):
            with pytest.raises(CorpusError, match="No Markdown documents"):
                load_chunks(Path("/guide/content/ru"))

    def test_rejects_duplicate_identifiers_across_documents(self):
        paths = [Path("/guide/content/ru/a.md"), Path("/guide/content/ru/b.md")]
        markdown = "# Карточки\n<!-- chunk_id: etch.cards.create -->\nТекст."

        with patch.object(Path, "glob", return_value=paths):
            with patch.object(Path, "read_text", return_value=markdown):
                with pytest.raises(CorpusError, match="duplicate chunk_id"):
                    load_chunks(Path("/guide/content/ru"))
