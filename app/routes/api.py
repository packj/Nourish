import calendar
from datetime import datetime, date
from flask import Blueprint, jsonify, request
from app.db import get_db_connection

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/calendar/<slug>")
def get_calendar_data(slug):
    conn = get_db_connection()
    m_set = conn.execute("SELECT * FROM missionary_sets WHERE slug = ? AND active = 1", (slug,)).fetchone()
    
    if not m_set:
        conn.close()
        return jsonify({"error": "Set not found"}), 404

    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Number of days in month
    num_days = calendar.monthrange(year, month)[1]
    start_date_str = f"{year:04d}-{month:02d}-01"
    end_date_str = f"{year:04d}-{month:02d}-{num_days:02d}"

    # Fetch confirmed bookings for this month
    bookings = conn.execute("""
        SELECT meal_date, meal_time, host_name, location_type
        FROM bookings
        WHERE set_id = ? AND status = 'confirmed' AND meal_date BETWEEN ? AND ?
    """, (m_set["id"], start_date_str, end_date_str)).fetchall()
    
    booked_map = {b["meal_date"]: dict(b) for b in bookings}

    # Fetch blackouts for this month
    blackouts = conn.execute("""
        SELECT blocked_date, reason
        FROM blackout_dates
        WHERE set_id = ? AND blocked_date BETWEEN ? AND ?
    """, (m_set["id"], start_date_str, end_date_str)).fetchall()

    blackout_map = {b["blocked_date"]: b["reason"] for b in blackouts}
    conn.close()

    days_data = []
    for day in range(1, num_days + 1):
        day_date = date(year, month, day)
        date_str = day_date.strftime("%Y-%m-%d")
        day_name = day_date.strftime("%A")

        is_past = day_date < today
        is_today = (day_date == today)

        status = "open"
        booking_info = None
        blackout_reason = None

        if is_past:
            status = "past"
        elif date_str in blackout_map:
            status = "blocked"
            blackout_reason = blackout_map[date_str]
        elif date_str in booked_map:
            status = "booked"
            booking_info = {
                "host_name": booked_map[date_str]["host_name"],
                "meal_time": booked_map[date_str]["meal_time"]
            }

        days_data.append({
            "day": day,
            "date": date_str,
            "day_name": day_name,
            "status": status,
            "is_today": is_today,
            "is_past": is_past,
            "booking": booking_info,
            "blocked_reason": blackout_reason
        })

    return jsonify({
        "set": {
            "id": m_set["id"],
            "name": m_set["name"],
            "slug": m_set["slug"],
            "default_time": m_set["default_time"],
            "dietary_restrictions": m_set["dietary_restrictions"]
        },
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "days": days_data
    })
