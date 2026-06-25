# AI Usage

I used AI tools during codebase navigation and debugging to move through the
project deliberately instead of guessing. The AI helped identify the likely
files for each layer, trace the stats and reading-history endpoints, compare
docstrings against implementations, and keep the two bugs separated as distinct
diagnoses.

I verified the AI-assisted reasoning by reading the relevant source files
directly, reseeding the database, running the Flask app, and checking the API
responses with curl. I did not rely on the AI output alone: the final fixes were
confirmed against the seeded behavior for Alex, Priya, and Marcus. I also kept
the changes smaller than a broad AI-generated refactor by making only the two
field changes supported by the code contracts and observed API output.

# Codebase Map

## Main Files And Roles

- `app.py`: creates the Flask app, configures SQLAlchemy, registers the route
  blueprints, and creates database tables.
- `models.py`: defines the database models: `User`, `Book`, and
  `ReadingEvent`.
- `routes/books.py`: exposes endpoints for listing and adding books.
- `routes/reading.py`: exposes endpoints for starting books, finishing books,
  viewing current reads, and viewing reading history.
- `routes/stats.py`: exposes the stats endpoint and delegates stat calculations
  to the service layer.
- `services/reading_service.py`: contains reading-list business logic,
  including creating reading events and querying reading history.
- `services/stats_service.py`: calculates reading streaks, books finished this
  month, and total pages read.
- `seed_data.py`: rebuilds the local database with sample users, books, and
  reading events for testing.

## Data Flow: User Stats

For `GET /stats/<user_id>`, the request enters `routes/stats.py` at
`get_stats()`. That route does not calculate stats itself. Instead, it calls
three service functions:

- `stats_service.calculate_streak(user_id)`
- `stats_service.books_this_month(user_id)`
- `stats_service.total_pages_read(user_id)`

Each stats function calls `reading_service.get_reading_history(user_id)` to get
only finished `ReadingEvent` records. Those events are connected to `Book`
records through the SQLAlchemy relationship, which allows `total_pages_read()`
to access `e.book.pages`.

The important model detail is that `ReadingEvent.started_at` is always set, but
`ReadingEvent.finished_at` can be `None`. A `finished_at` value of `None` means
the book is still in progress, so finished-book stats must use records where
`finished_at` is set. The unique constraint on `ReadingEvent` prevents the same
user from having more than one reading event for the same book.

The full call chain for the streak feature is: HTTP request ->
`routes/stats.py` -> `stats_service.calculate_streak()` ->
`reading_service.get_reading_history()` -> `ReadingEvent`. The stats endpoint
does not use the `User.reading_streak` column; it computes the streak live from
finished reading events.

# Root Cause Analysis

## Bug 1: Reading Streak Returned 0

Observed behavior: Alex's stats endpoint returned `reading_streak: 0` even
though Alex had finished books on three consecutive calendar days.

Expected behavior: Alex's streak should be `3`, based on finished books on
June 23, June 24, and June 25, 2026.

Root cause: `calculate_streak()` was building its date set from
`e.started_at.date()`. The function docstring defines a streak as consecutive
days on which the user finished at least one book, so `started_at` was the wrong
field. It was a valid date field, which made the bug look plausible, but it did
not match the feature contract.

Diagnosis template:

- The docstring says: count consecutive calendar days on which the user
  finished at least one book.
- The code does: collects dates from `e.started_at.date()`, which is when the
  user began each book.
- The bug is on line: the date-set comprehension in `calculate_streak()`.
- The fix is: change `started_at` to `finished_at`.

Fix: Changed the streak calculation to use `e.finished_at.date()`.

Verification: After the fix, Alex's stats returned `reading_streak: 3`,
`books_this_month: 3`, and `total_pages_read: 814`. The other stat values stayed
correct.

## Bug 2: Reading History Was In The Wrong Order

Observed behavior: Alex's history endpoint returned the correct finished books,
but listed `Giovanni's Room` first even though it was not the most recently
finished book.

Expected behavior: The history endpoint should return finished books most
recently finished first.

Root cause: `get_reading_history()` filtered correctly to finished events, but
ordered those events by `ReadingEvent.started_at.desc()`. The route and service
docstrings both promised most-recently-finished first, so the query needed to
sort by `finished_at`, not `started_at`.

Diagnosis template:

- The docstring says: return finished books most recently finished first.
- The code does: orders finished events by `ReadingEvent.started_at.desc()`.
- The bug is on line: the `order_by()` clause in `get_reading_history()`.
- The fix is: change `started_at.desc()` to `finished_at.desc()`.

Fix: Changed the history query to order by `ReadingEvent.finished_at.desc()`.

Verification: After the fix, Alex's history listed `The Left Hand of Darkness`
first with the June 25, 2026 finish timestamp. Priya's history also returned
the June 18 finish before the June 17 finish. Alex's streak remained `3`, while
Priya's and Marcus's streaks were both `0`.

# Discussion Reflection

Thorough verification changed what I found because fixing the streak did not end
the investigation. After the first fix, the stats endpoint was correct, but
checking the related history endpoint showed that the books were still displayed
in the wrong order. If I had stopped after confirming `reading_streak: 3`, I
would have missed the second bug entirely.

The two bugs also showed the difference between a logic bug and a display bug.
Bug 1 returned the wrong computed value because the calculation used start dates
instead of finish dates. Bug 2 returned the right records with the right dates,
but presented them in the wrong order. They both involved `started_at` where
`finished_at` belonged, but they were different categories of mistake.
