import re
from functools import wraps
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.db import get_db_connection
from app.config import Config
from app.services.sheets_sync import sync_missionary_set_to_sheets, APPS_SCRIPT_TEMPLATE

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if password == Config.ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Logged into Admin Dashboard.", "success")
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)
        else:
            flash("Incorrect admin password.", "error")

    return render_template("admin/login.html")

@admin_bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("public.index"))

@admin_bp.route("/")
@admin_required
def dashboard():
    conn = get_db_connection()
    sets = conn.execute("SELECT * FROM missionary_sets ORDER BY id ASC").fetchall()
    
    # Upcoming meals across all sets (next 14 days)
    upcoming = conn.execute("""
        SELECT b.*, m.name as set_name, m.slug as set_slug
        FROM bookings b
        JOIN missionary_sets m ON b.set_id = m.id
        WHERE b.status = 'confirmed' AND b.meal_date >= date('now', 'localtime')
        ORDER BY b.meal_date ASC
        LIMIT 20
    """).fetchall()

    # Total confirmed counts
    total_stats = conn.execute("""
        SELECT COUNT(*) as total_upcoming
        FROM bookings
        WHERE status = 'confirmed' AND meal_date >= date('now', 'localtime')
    """).fetchone()

    conn.close()
    return render_template(
        "admin/dashboard.html",
        sets=sets,
        upcoming=upcoming,
        total_upcoming=total_stats["total_upcoming"] if total_stats else 0
    )

@admin_bp.route("/sets/new", methods=["GET", "POST"])
@admin_required
def new_set():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        default_time = request.form.get("default_time", "5:00 PM").strip()
        dietary_restrictions = request.form.get("dietary_restrictions", "").strip()
        notes = request.form.get("notes", "").strip()
        sync_mode = request.form.get("sync_mode", "webhook").strip()
        google_webhook_url = request.form.get("google_webhook_url", "").strip()
        google_sheet_id = request.form.get("google_sheet_id", "").strip()
        google_sheet_tab = request.form.get("google_sheet_tab", "").strip()

        if not name:
            flash("Companionship / Set name is required.", "error")
            return render_template("admin/set_form.html", m_set={}, is_edit=False)

        base_slug = slugify(name)
        slug = base_slug
        conn = get_db_connection()
        
        # Ensure unique slug
        counter = 1
        while conn.execute("SELECT id FROM missionary_sets WHERE slug = ?", (slug,)).fetchone():
            slug = f"{base_slug}-{counter}"
            counter += 1

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO missionary_sets (name, slug, phone, email, default_time, dietary_restrictions,
                                        notes, sync_mode, google_webhook_url, google_sheet_id, google_sheet_tab)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, slug, phone, email, default_time, dietary_restrictions, notes,
              sync_mode, google_webhook_url, google_sheet_id, google_sheet_tab))
        set_id = cursor.lastrowid
        conn.commit()
        conn.close()

        flash(f"Missionary set '{name}' created successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/set_form.html", m_set={}, is_edit=False)

@admin_bp.route("/sets/<int:set_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_set(set_id):
    conn = get_db_connection()
    m_set = conn.execute("SELECT * FROM missionary_sets WHERE id = ?", (set_id,)).fetchone()
    
    if not m_set:
        conn.close()
        flash("Missionary set not found.", "error")
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        default_time = request.form.get("default_time", "5:00 PM").strip()
        dietary_restrictions = request.form.get("dietary_restrictions", "").strip()
        notes = request.form.get("notes", "").strip()
        active = 1 if request.form.get("active") else 0
        sync_mode = request.form.get("sync_mode", "webhook").strip()
        google_webhook_url = request.form.get("google_webhook_url", "").strip()
        google_sheet_id = request.form.get("google_sheet_id", "").strip()
        google_sheet_tab = request.form.get("google_sheet_tab", "").strip()

        if not name:
            flash("Companionship / Set name is required.", "error")
            conn.close()
            return render_template("admin/set_form.html", m_set=m_set, is_edit=True)

        conn.execute("""
            UPDATE missionary_sets
            SET name = ?, phone = ?, email = ?, default_time = ?, dietary_restrictions = ?,
                notes = ?, active = ?, sync_mode = ?, google_webhook_url = ?,
                google_sheet_id = ?, google_sheet_tab = ?
            WHERE id = ?
        """, (name, phone, email, default_time, dietary_restrictions, notes, active,
              sync_mode, google_webhook_url, google_sheet_id, google_sheet_tab, set_id))
        conn.commit()
        conn.close()

        flash(f"Updated '{name}' settings.", "success")
        return redirect(url_for("admin.dashboard"))

    conn.close()
    return render_template("admin/set_form.html", m_set=m_set, is_edit=True)

@admin_bp.route("/sets/<int:set_id>/delete", methods=["POST"])
@admin_required
def delete_set(set_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM missionary_sets WHERE id = ?", (set_id,))
    conn.commit()
    conn.close()
    flash("Missionary set and its associated records were deleted.", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/sets/<int:set_id>/sync", methods=["POST"])
@admin_required
def trigger_sync(set_id):
    result = sync_missionary_set_to_sheets(set_id)
    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(f"Sync failed: {result['message']}", "error")
    
    return redirect(request.referrer or url_for("admin.dashboard"))

@admin_bp.route("/sets/<int:set_id>/calendar")
@admin_required
def set_calendar(set_id):
    conn = get_db_connection()
    m_set = conn.execute("SELECT * FROM missionary_sets WHERE id = ?", (set_id,)).fetchone()
    
    if not m_set:
        conn.close()
        flash("Missionary set not found.", "error")
        return redirect(url_for("admin.dashboard"))

    bookings = conn.execute("""
        SELECT * FROM bookings
        WHERE set_id = ?
        ORDER BY meal_date DESC
    """, (set_id,)).fetchall()

    blackouts = conn.execute("""
        SELECT * FROM blackout_dates
        WHERE set_id = ?
        ORDER BY blocked_date ASC
    """, (set_id,)).fetchall()

    conn.close()
    return render_template(
        "admin/set_calendar.html",
        m_set=m_set,
        bookings=bookings,
        blackouts=blackouts,
        today=date.today().strftime("%Y-%m-%d")
    )

@admin_bp.route("/sets/<int:set_id>/admin-book", methods=["POST"])
@admin_required
def admin_add_booking(set_id):
    import secrets
    conn = get_db_connection()
    meal_date = request.form.get("meal_date", "").strip()
    host_name = request.form.get("host_name", "").strip()
    host_phone = request.form.get("host_phone", "").strip()
    meal_time = request.form.get("meal_time", "5:00 PM").strip()
    location_type = request.form.get("location_type", "home").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()

    if not meal_date or not host_name or not host_phone:
        flash("Date, Host Name, and Phone are required.", "error")
        conn.close()
        return redirect(url_for("admin.set_calendar", set_id=set_id))

    # Cancel any active existing booking on that day if overriding
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE set_id = ? AND meal_date = ?", (set_id, meal_date))
    cancel_code = secrets.token_hex(3).upper()

    conn.execute("""
        INSERT INTO bookings (set_id, meal_date, meal_time, host_name, host_phone, location_type, address, notes, cancel_code, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
    """, (set_id, meal_date, meal_time, host_name, host_phone, location_type, address, notes, cancel_code))
    conn.commit()
    conn.close()

    try:
        sync_missionary_set_to_sheets(set_id)
    except Exception:
        pass

    flash(f"Booking added for {host_name} on {meal_date}.", "success")
    return redirect(url_for("admin.set_calendar", set_id=set_id))

@admin_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_booking(booking_id):
    conn = get_db_connection()
    booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking:
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        conn.commit()
        set_id = booking["set_id"]
        conn.close()
        try:
            sync_missionary_set_to_sheets(set_id)
        except Exception:
            pass
        flash("Booking cancelled.", "info")
        return redirect(url_for("admin.set_calendar", set_id=set_id))
    
    conn.close()
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/sets/<int:set_id>/blackout/add", methods=["POST"])
@admin_required
def add_blackout(set_id):
    blocked_date = request.form.get("blocked_date", "").strip()
    reason = request.form.get("reason", "Unavailable").strip()
    
    if not blocked_date:
        flash("Please select a date to block.", "error")
        return redirect(url_for("admin.set_calendar", set_id=set_id))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO blackout_dates (set_id, blocked_date, reason)
            VALUES (?, ?, ?)
        """, (set_id, blocked_date, reason))
        conn.commit()
        flash(f"Blocked {blocked_date} ({reason}).", "success")
    except Exception:
        flash(f"Date {blocked_date} is already blocked.", "error")
    finally:
        conn.close()

    return redirect(url_for("admin.set_calendar", set_id=set_id))

@admin_bp.route("/blackout/<int:blackout_id>/delete", methods=["POST"])
@admin_required
def delete_blackout(blackout_id):
    conn = get_db_connection()
    row = conn.execute("SELECT set_id FROM blackout_dates WHERE id = ?", (blackout_id,)).fetchone()
    set_id = row["set_id"] if row else None
    conn.execute("DELETE FROM blackout_dates WHERE id = ?", (blackout_id,))
    conn.commit()
    conn.close()
    
    flash("Date unblocked.", "info")
    if set_id:
        return redirect(url_for("admin.set_calendar", set_id=set_id))
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/sheets-setup")
@admin_required
def sheets_setup():
    return render_template("admin/sheets_setup.html", script_template=APPS_SCRIPT_TEMPLATE)
