from datetime import datetime, timezone

import pytest

from app import create_app
from extensions import db
from models import Book, ReadingEvent, User
from services import reading_service, stats_service


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(username="alex"):
    user = User(username=username, email=f"{username}@bookclub.test")
    db.session.add(user)
    db.session.flush()
    return user


def make_book(user, title, genre="sci-fi", pages=100):
    book = Book(
        title=title,
        author="Test Author",
        pages=pages,
        genre=genre,
        added_by=user.id,
    )
    db.session.add(book)
    db.session.flush()
    return book


def make_event(user, book, started_at, finished_at):
    event = ReadingEvent(
        user_id=user.id,
        book_id=book.id,
        started_at=started_at,
        finished_at=finished_at,
    )
    db.session.add(event)
    db.session.flush()
    return event


def utc_datetime(year, month, day, hour=12, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_calculate_streak_uses_finished_dates(app):
    with app.app_context():
        user = make_user()
        books = [make_book(user, f"Book {i}") for i in range(3)]
        finished_dates = [
            utc_datetime(2026, 6, 25),
            utc_datetime(2026, 6, 24),
            utc_datetime(2026, 6, 23),
        ]
        for book, finished_at in zip(books, finished_dates):
            make_event(
                user,
                book,
                started_at=utc_datetime(2026, 1, 1),
                finished_at=finished_at,
            )
        db.session.commit()

        streak = stats_service.calculate_streak(
            user.id,
            now=utc_datetime(2026, 6, 25, 18),
        )

        assert streak == 3


def test_calculate_streak_converts_finished_dates_to_local_timezone(app):
    with app.app_context():
        user = make_user()
        book_one = make_book(user, "Late Local Finish")
        book_two = make_book(user, "Early UTC Finish")
        make_event(
            user,
            book_one,
            started_at=utc_datetime(2026, 1, 1),
            finished_at=utc_datetime(2026, 6, 25, 23, 30),
        )
        make_event(
            user,
            book_two,
            started_at=utc_datetime(2026, 1, 2),
            finished_at=utc_datetime(2026, 6, 25, 4, 30),
        )
        db.session.commit()

        chicago_streak = stats_service.calculate_streak(
            user.id,
            timezone_name="America/Chicago",
            now=utc_datetime(2026, 6, 25, 23, 45),
        )
        utc_streak = stats_service.calculate_streak(
            user.id,
            timezone_name="UTC",
            now=utc_datetime(2026, 6, 25, 23, 45),
        )

        assert chicago_streak == 2
        assert utc_streak == 1


def test_get_reading_history_orders_by_finished_at(app):
    with app.app_context():
        user = make_user()
        older_finish = make_book(user, "Started Later Finished Earlier")
        newer_finish = make_book(user, "Started Earlier Finished Later")
        make_event(
            user,
            older_finish,
            started_at=utc_datetime(2026, 6, 20),
            finished_at=utc_datetime(2026, 6, 23),
        )
        make_event(
            user,
            newer_finish,
            started_at=utc_datetime(2026, 6, 1),
            finished_at=utc_datetime(2026, 6, 25),
        )
        db.session.commit()

        history = reading_service.get_reading_history(user.id)

        assert [event.book.title for event in history] == [
            "Started Earlier Finished Later",
            "Started Later Finished Earlier",
        ]


def test_genre_streak_route_counts_matching_genre_case_insensitively(app, client):
    with app.app_context():
        user = make_user()
        sci_fi_today = make_book(user, "Today", genre="sci-fi")
        sci_fi_yesterday = make_book(user, "Yesterday", genre="Sci-Fi")
        other_genre = make_book(user, "Other", genre="memoir")
        make_event(
            user,
            sci_fi_today,
            started_at=utc_datetime(2026, 1, 1),
            finished_at=utc_datetime(2026, 6, 25),
        )
        make_event(
            user,
            sci_fi_yesterday,
            started_at=utc_datetime(2026, 1, 2),
            finished_at=utc_datetime(2026, 6, 24),
        )
        make_event(
            user,
            other_genre,
            started_at=utc_datetime(2026, 1, 3),
            finished_at=utc_datetime(2026, 6, 23),
        )
        db.session.commit()

        response = client.get(
            f"/stats/{user.id}/genre-streak/SCI-FI",
            query_string={"timezone": "UTC"},
        )

        assert response.status_code == 200
        assert response.json["genre_streak"] == 2
        assert response.json["genre"] == "SCI-FI"
