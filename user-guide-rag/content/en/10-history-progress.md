# Etch: continue an unfinished practice session
<!-- chunk_id: etch.history.resume -->

Open “Practice” and the “in progress” filter. Find your session and select “Continue”. Etch loads its remaining cards and saved answer counters.

You can also open a saved link such as `/practice?session=session_identifier` while signed in to the same account. A completed session cannot be continued; use “Repeat” for another attempt.

Continuing requires an available deck. If it was archived, first check whether it can be restored in “Deck archive”. Closing the page does not itself complete the session.

<!-- RAG_CHUNK -->

# Etch: view a session's answer history
<!-- chunk_id: etch.history.answers -->

Find a session in “Practice” and select “Open session history”. History shows each prompt, its correct answer, your typed answer, and the card's status.

Statuses are “Correct”, “Incorrect”, “Skipped”, and “Not answered”. “Skipped” means you selected “I don't know”; “Not answered” means no answer has been submitted yet.

The history summary shows wrong answers and skips separately. The practice session's incorrect-answer counter includes skips, so it may differ from the number of “Incorrect” entries.

History stores the texts captured when the session was created. Editing cards later does not change the old prompts or answers in history.

<!-- RAG_CHUNK -->

# Etch: filter practice sessions
<!-- chunk_id: etch.history.filters -->

“Practice” has “all”, “completed”, “in progress”, and “abandoned” filters. They change which sessions are displayed without deleting data.

Use “Continue” for an unfinished session if its deck is available. To start another session, select “New session” and choose a deck.

The “abandoned” filter displays sessions with that status when such records exist. Its presence does not mean leaving the page automatically marks a session as abandoned. The current interface has no separate “Abandon session” button.

<!-- RAG_CHUNK -->

# Etch: deck accuracy and home page metrics
<!-- chunk_id: etch.progress.accuracy -->

Etch calculates deck accuracy from your answers in completed sessions for that deck: correct answers divided by the total of correct and incorrect answers, multiplied by 100. The fractional part is discarded; without answers, it shows 0%.

“Accuracy” under “This week” on the home page uses answers from the last seven calendar days, including today, in completed sessions. This percentage is rounded to a whole number. It may differ from the overall accuracy of a particular deck.

If the deck's progress has not changed after a few answers, finish the entire session: its results are added to deck metrics on completion.

<!-- RAG_CHUNK -->

# Etch: studied cards, daily streak, and study time
<!-- chunk_id: etch.progress.summary -->

“Studied” on the Etch home page counts distinct learning cards by their stored learning identifiers that have answers in completed sessions. It does not mean every counted word was answered correctly or permanently mastered.

“Current streak” is a sequence of days with answers from completed sessions. Days are counted in UTC. A streak remains current when its latest active day is today or yesterday; otherwise the value is 0.

“Study time” totals the active time of completed sessions. An idle open tab and an unfinished session should not be treated as time already added to this total.

<!-- RAG_CHUNK -->

# Etch: understand the weekly activity chart
<!-- chunk_id: etch.progress.activity -->

“Weekly activity” on the Etch home page shows cards processed per day over the last seven days. Its unit is card answers, not minutes or newly created words.

Activity includes processed cards, including wrong answers and skips, even when their session is unfinished. Practicing the same card again in a new session adds another answer to activity.

Overall progress metrics and deck accuracy use completed sessions. The activity chart can therefore change before overall progress does.
