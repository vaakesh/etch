# Etch: set up a practice session
<!-- chunk_id: etch.practice.setup -->

Select “Start practice” for an available deck. In “Session setup”, choose the direction: which side you see and which side you type. The “Example” section shows “You will see” and “You will type”.

Choose the length: the entire deck, 50, 100, or a custom number of cards. A custom value must be a whole number from 1 to 500. A deck with more than 500 cards cannot be practiced in full in one session.

Select “Start practice”. If you request more cards than the deck contains, the session uses the available number. An empty deck cannot be practiced. When practicing part of a deck, cards are selected randomly.

<!-- RAG_CHUNK -->

# Etch: answer cards during practice
<!-- chunk_id: etch.practice.answer -->

During practice, Etch displays a prompt and a “Your answer” field. Type the text from the other side of the card and select “Submit answer”.

Etch checks your answer and shows the result and correct answer. Select “Next” to move to the next card, or “Results” after the last one. Navigation controls let you view session cards.

If you do not know the answer, select “I don't know”. This skip counts as an incorrect answer in session counters. Detailed history marks skipped cards separately. An empty string cannot be submitted as a regular answer.

<!-- RAG_CHUNK -->

# Etch: why a similar meaning can still be marked incorrect
<!-- chunk_id: etch.practice.matching -->

Etch compares your input with the stored text of the expected card side. It ignores letter case and leading or trailing whitespace. For example, ` Hello ` is accepted when the expected answer is `hello`.

Internal spaces, punctuation, typos, and different spellings are not automatically corrected. Synonyms and alternative translations are not checked for meaning. If the card expects `hello`, entering `hi` is marked incorrect.

Several alternatives written with commas or slashes on one card side are treated as a single answer string, not a list of accepted alternatives. Use one expected answer per card for straightforward checking.

<!-- RAG_CHUNK -->

# Etch: pause and full-screen practice
<!-- chunk_id: etch.practice.pause -->

Etch pauses practice after about two minutes without interaction. The “Practice paused” message asks you to click anywhere to continue.

Hiding the tab also pauses activity tracking. Study time measures active practice, so the tab may have been open longer than the time displayed for your session.

“Full screen” enables full-screen mode when supported by your browser. Use “Exit full screen” to return. Pausing or changing the screen mode does not complete the session.

<!-- RAG_CHUNK -->

# Etch: finish or repeat a practice session
<!-- chunk_id: etch.practice.finish -->

An Etch session finishes when every selected card has either a submitted answer or an “I don't know” response. The results screen shows correct answers, errors, accuracy, and time.

For another attempt, use “Practice again” on the results screen or “Repeat” on a completed session in “Practice”. Repeating starts a new session; earlier answers remain in history.

An accepted answer cannot be replaced within the current session. To work on mistakes, review the correct answers in history and start a new session with an available deck.
