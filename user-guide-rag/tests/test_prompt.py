from rag.prompt import build_messages


class TestBuildMessages:
    def test_includes_full_fragment_and_original_question(self, hit):
        messages = build_messages("Как создать карточку?", [hit])

        assert messages[0]["role"] == "system"
        assert messages[1] == {
            "role": "user",
            "content": (
                "Фрагменты справки:\n<context>\n"
                "[1] content/ru/05-cards.md (etch.cards.create)\n"
                "# Etch: как создать карточку\n\nНажмите «Новая карточка»."
                "\n</context>\n\nВопрос: Как создать карточку?"
            ),
        }
