"""
routes/stats.py — BookClub

Routes for reading statistics: streak, books this month, total pages read.
"""

from flask import Blueprint, jsonify, request
from services import stats_service

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/<user_id>", methods=["GET"])
def get_stats(user_id):
    """
    Return reading statistics for a user.

    Response JSON:
        reading_streak    (int) — consecutive days with at least one book finished
        books_this_month  (int) — books finished in the current calendar month
        total_pages_read  (int) — total pages across all finished books
    """
    timezone_name = request.args.get("timezone", "UTC")
    try:
        reading_streak = stats_service.calculate_streak(user_id, timezone_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "user_id": user_id,
            "reading_streak": reading_streak,
            "books_this_month": stats_service.books_this_month(user_id),
            "total_pages_read": stats_service.total_pages_read(user_id),
        }
    )
