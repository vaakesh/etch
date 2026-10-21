# Etch: import cards from JSON
<!-- chunk_id: etch.import.steps -->

Select “Import” in the library. Choose your own deck, proceed to JSON entry, then paste the text or select “Open .json”. After checking it, select “Import” and wait for confirmation.

New cards are added to the end of the selected deck. Each import accepts 1–500 cards. The deck must contain no more than 5000 cards after the import, including its existing cards.

If your deck is missing from the import list, close the dialog, create or load your deck in the library, and open import again. Someone else's saved deck cannot receive your imported cards.

<!-- RAG_CHUNK -->

# Etch: JSON example for importing cards
<!-- chunk_id: etch.import.format -->

Etch import accepts an object with a required `cards` array. Each card needs `front_text` and `back_text`. Example:

```json
{
  "cards": [
    {
      "front_text": "привет",
      "back_text": "hello",
      "front_lang": "ru",
      "back_lang": "en"
    },
    {
      "front_text": "спасибо",
      "back_text": "thank you",
      "front_lang": "ru",
      "back_lang": "en"
    }
  ]
}
```

`front_text` and `back_text` are the two card sides. In the manual editor, `back_text` corresponds to “Foreign word” and `front_text` to “Translation”. Languages are optional: `front_lang` defaults to `ru` and `back_lang` to `en`. Specify the codes explicitly for a different language pair.

Paste the JSON itself into the import field without Markdown triple-backtick fences.

<!-- RAG_CHUNK -->

# Etch: fix JSON import errors and size limits
<!-- chunk_id: etch.import.errors -->

If Etch rejects an import, check the following:

- The root is an object with a `cards` array, not an array on its own.
- The array contains 1–500 card objects.
- `front_text` and `back_text` are non-empty strings of up to 255 characters after trimming leading and trailing whitespace.
- Language codes, when provided, contain 2–3 Latin letters.
- Strings use double quotes, the last item has no trailing comma, and all brackets and braces are closed.
- The deck has enough space within its 5000-card limit.

An error path such as `cards[0].front_text` refers to the first card; `cards[1]` refers to the second. If the file cannot be read, try pasting its JSON manually.
