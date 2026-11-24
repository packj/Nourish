from datetime import datetime, timedelta

def generate_ics(booking, set_info):
    """
    Generates an iCalendar (.ics) format string so the member can add
    the dinner appointment to Apple Calendar, Google Calendar, or Outlook.
    """
    meal_date = booking["meal_date"]  # YYYY-MM-DD
    meal_time = booking.get("meal_time", "5:00 PM")
    set_name = set_info["name"]
    host_name = booking["host_name"]

    # Try parsing time
    try:
        time_part = datetime.strptime(meal_time.strip(), "%I:%M %p")
        date_part = datetime.strptime(meal_date, "%Y-%m-%d")
        dt_start = datetime.combine(date_part.date(), time_part.time())
    except Exception:
        # Fallback to 5:00 PM
        date_part = datetime.strptime(meal_date, "%Y-%m-%d")
        dt_start = datetime.combine(date_part.date(), datetime.strptime("17:00", "%H:%M").time())

    dt_end = dt_start + timedelta(hours=1)
    
    start_str = dt_start.strftime("%Y%m%dT%H%M%S")
    end_str = dt_end.strftime("%Y%m%dT%H%M%S")
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    summary = f"Feed the Missionaries ({set_name})"
    description = f"Host: {host_name}\\nMissionary Contact: {set_info.get('phone', 'N/A')}\\nDietary Notes: {set_info.get('dietary_restrictions', 'None')}"
    if booking.get("notes"):
        description += f"\\nHost Notes: {booking['notes']}"
    
    location = booking.get("address") or "Host's home"

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nourish//Missionary Dinner Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:nourish-booking-{booking['id']}@nourish.local
DTSTAMP:{now_str}
DTSTART:{start_str}
DTEND:{end_str}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    return ics_content.replace("\n", "\r\n")
