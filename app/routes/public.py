import secrets
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from app.db import get_db_connection
from app.services.sheets_sync import sync_missionary_set_to_sheets
from app.services.ical_generator import generate_ics

public_bp = Blueprint("public", __name__)

@public_bp.route("/")
def index():
    conn = get_db_connection()
    sets = conn.execute("SELECT * FROM missionary_sets WHERE active = 1 ORDER BY id ASC").fetchall()
    conn.close()

    if not sets:
        return render_template("no_sets.html")
    
    # If there's only one set, redirect directly to its calendar
    if len(sets) == 1:
        return redirect(url_for("public.view_set_calendar", slug=sets[0]["slug"]))
    
    return render_template("index.html", sets=sets)

@public_bp.route("/set/<slug>")
def view_set_calendar(slug):
    conn = get_db_connection()
    m_set = conn.execute("SELECT * FROM missionary_sets WHERE slug = ? AND active = 1", (slug,)).fetchone()
    all_sets = conn.execute("SELECT id, name, slug FROM missionary_sets WHERE active = 1 ORDER BY id ASC").fetchall()
    
    if not m_set:
        conn.close()
        flash("Missionary set not found or inactive.", "error")
        return redirect(url_for("public.index"))

    # Selected year and month (default to today)
    today = date.today()
    try:
        req_year = int(request.args.get("year", today.year))
        req_month = int(request.args.get("month", today.month))
        # Basic bounds check
        if req_month < 1 or req_month > 12 or req_year < 2020 or req_year > 2040:
            req_year, req_month = today.year, today.month
    except (ValueError, TypeError):
        req_year, req_month = today.year, today.month

    conn.close()
    return render_template(
        "calendar.html",
        current_set=m_set,
        all_sets=all_sets,
        year=req_year,
        month=req_month,
        today=today.strftime("%Y-%m-%d")
    )

@public_bp.route("/set/<slug>/book", methods=["POST"])
def book_meal(slug):
    conn = get_db_connection()
    m_set = conn.execute("SELECT * FROM missionary_sets WHERE slug = ? AND active = 1", (slug,)).fetchone()
    
    if not m_set:
        conn.close()
        flash("Missionary set not found.", "error")
        return redirect(url_for("public.index"))

    meal_date = request.form.get("meal_date", "").strip()
    host_name = request.form.get("host_name", "").strip()
    host_phone = request.form.get("host_phone", "").strip()
    meal_time = request.form.get("meal_time", "").strip() or m_set["default_time"]
    location_type = request.form.get("location_type", "home").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()
    host_email = request.form.get("host_email", "").strip()

    # Validations
    if not meal_date or not host_name or not host_phone:
        flash("Please provide your name, phone number, and select a date.", "error")
        conn.close()
        return redirect(url_for("public.view_set_calendar", slug=slug))

    try:
        book_dt = datetime.strptime(meal_date, "%Y-%m-%d").date()
        if book_dt < date.today():
            flash("You cannot sign up for a date in the past.", "error")
            conn.close()
            return redirect(url_for("public.view_set_calendar", slug=slug))
    except ValueError:
        flash("Invalid date format.", "error")
        conn.close()
        return redirect(url_for("public.view_set_calendar", slug=slug))

    # Check for blackout
    blackout = conn.execute("SELECT id, reason FROM blackout_dates WHERE set_id = ? AND blocked_date = ?", (m_set["id"], meal_date)).fetchone()
    if blackout:
        flash(f"That date is unavailable: {blackout['reason']}", "error")
        conn.close()
        return redirect(url_for("public.view_set_calendar", slug=slug))

    # Check for existing booking
    existing = conn.execute("SELECT id FROM bookings WHERE set_id = ? AND meal_date = ? AND status = 'confirmed'", (m_set["id"], meal_date)).fetchone()
    if existing:
        flash("Someone has already signed up for this date! Please choose another open day.", "error")
        conn.close()
        return redirect(url_for("public.view_set_calendar", slug=slug))

    # Generate random cancel code (e.g. 6 chars)
    cancel_code = secrets.token_hex(3).upper()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bookings (set_id, meal_date, meal_time, host_name, host_phone, host_email, location_type, address, notes, cancel_code, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
    """, (m_set["id"], meal_date, meal_time, host_name, host_phone, host_email, location_type, address, notes, cancel_code))
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Trigger Google Sheets sync
    try:
        sync_missionary_set_to_sheets(m_set["id"])
    except Exception as e:
        # Don't fail booking if sheet sync had an issue
        pass

    flash("Thank you for signing up to feed the missionaries!", "success")
    return redirect(url_for("public.booking_confirm", booking_id=booking_id, code=cancel_code))

@public_bp.route("/booking/<int:booking_id>/confirm")
def booking_confirm(booking_id):
    code = request.args.get("code", "")
    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.*, m.name as set_name, m.slug as set_slug, m.phone as missionary_phone,
               m.dietary_restrictions, m.notes as set_notes
        FROM bookings b
        JOIN missionary_sets m ON b.set_id = m.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    conn.close()

    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for("public.index"))

    return render_template("booked_confirm.html", booking=booking, code=code)

@public_bp.route("/booking/<int:booking_id>/cancel", methods=["GET", "POST"])
def cancel_booking(booking_id):
    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.*, m.name as set_name, m.slug as set_slug
        FROM bookings b
        JOIN missionary_sets m ON b.set_id = m.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()

    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("public.index"))

    provided_code = request.args.get("code") or request.form.get("code", "").strip().upper()

    if request.method == "POST":
        if provided_code != booking["cancel_code"]:
            flash("Invalid cancellation PIN / code.", "error")
            conn.close()
            return render_template("cancel_booking.html", booking=booking, code=provided_code)

        conn.execute("UPDATE bookings SET status = 'cancelled', updated_at = datetime('now', 'localtime') WHERE id = ?", (booking_id,))
        conn.commit()
        set_id = booking["set_id"]
        set_slug = booking["set_slug"]
        conn.close()

        # Resync sheet to remove or update
        try:
            sync_missionary_set_to_sheets(set_id)
        except Exception:
            pass

        flash("Your meal sign-up has been successfully cancelled. The date is now open for others.", "info")
        return redirect(url_for("public.view_set_calendar", slug=set_slug))

    conn.close()
    return render_template("cancel_booking.html", booking=booking, code=provided_code)

@public_bp.route("/booking/<int:booking_id>/ical")
def download_ical(booking_id):
    conn = get_db_connection()
    booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        conn.close()
        return "Booking not found", 404
    
    set_info = conn.execute("SELECT * FROM missionary_sets WHERE id = ?", (booking["set_id"],)).fetchone()
    conn.close()

    ics_data = generate_ics(booking, set_info)
    filename = f"missionary-dinner-{booking['meal_date']}.ics"
    return Response(
        ics_data,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
