import requests
import json
import logging
from datetime import datetime
from app.db import get_db_connection

logger = logging.getLogger(__name__)

# Pre-packaged Google Apps Script that ward clerks/missionary leaders can paste into their Sheet
APPS_SCRIPT_TEMPLATE = """/**
 * Nourish - Missionary Dinner Calendar Sync Script
 * ------------------------------------------------
 * Instructions:
 * 1. In your Google Sheet, click Extensions > Apps Script.
 * 2. Delete any existing code, paste this entire script, and click Save (disk icon).
 * 3. Click 'Deploy' (top right) > 'New deployment'.
 * 4. Select type: 'Web app'.
 * 5. Set:
 *    - Description: "Nourish Calendar Sync"
 *    - Execute as: "Me"
 *    - Who has access: "Anyone"
 * 6. Click 'Deploy', authorize access if prompted, and copy the Web App URL.
 * 7. Paste that URL into the Missionary Set's settings in the Nourish Admin dashboard!
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    
    // Set sheet tab title if provided
    if (data.set_name) {
      try { sheet.setName(data.set_name + " Dinners"); } catch(err) {}
    }

    // Reset and build headers
    sheet.clear();
    
    // Header Info Banner
    sheet.getRange(1, 1).setValue("🍽️ Missionary Meal Calendar: " + (data.set_name || "Companionship"));
    sheet.getRange(1, 1).setFontSize(14).setFontWeight("bold");
    
    if (data.dietary_restrictions) {
      sheet.getRange(2, 1).setValue("⚠️ Dietary Notes / Allergies: " + data.dietary_restrictions);
      sheet.getRange(2, 1).setFontStyle("italic").setFontColor("#b91c1c");
    }
    
    sheet.getRange(3, 1).setValue("Last Updated: " + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss"));
    sheet.getRange(3, 1).setFontColor("#6b7280").setFontSize(9);

    // Table Headers
    var headers = ["Date", "Day", "Time", "Host Name", "Phone Number", "Meal / Location", "Address", "Notes", "Status"];
    var startRow = 5;
    
    var headerRange = sheet.getRange(startRow, 1, 1, headers.length);
    headerRange.setValues([headers]);
    headerRange.setBackground("#1e3a8a").setFontColor("#ffffff").setFontWeight("bold");
    
    // Populate Data
    var bookings = data.bookings || [];
    if (bookings.length > 0) {
      var rows = bookings.map(function(b) {
        return [
          b.date || "",
          b.day_of_week || "",
          b.time || "",
          b.host_name || "",
          b.host_phone || "",
          b.location_type || "",
          b.address || "",
          b.notes || "",
          b.status || "confirmed"
        ];
      });
      
      var dataRange = sheet.getRange(startRow + 1, 1, rows.length, headers.length);
      dataRange.setValues(rows);
      
      // Alternating row background
      for (var i = 0; i < rows.length; i++) {
        var rowRange = sheet.getRange(startRow + 1 + i, 1, 1, headers.length);
        if (i % 2 === 1) {
          rowRange.setBackground("#f8fafc");
        }
      }
    } else {
      sheet.getRange(startRow + 1, 1).setValue("No upcoming dinners scheduled yet.");
      sheet.getRange(startRow + 1, 1, 1, headers.length).setFontStyle("italic").setFontColor("#9ca3af");
    }

    // Auto-fit column widths
    for (var c = 1; c <= headers.length; c++) {
      sheet.autoResizeColumn(c);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      count: bookings.length,
      synced_at: new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);

  } catch(error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput("Nourish Google Sheets Webhook is active and listening for POST requests.");
}
"""

def format_day_of_week(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%A")
    except Exception:
        return ""

def format_location_label(loc_type):
    labels = {
        "home": "At Host Home",
        "delivery": "Drop off at Apartment",
        "church": "Eat at Church Building",
        "other": "Other"
    }
    return labels.get(loc_type, loc_type.capitalize() if loc_type else "")

def get_set_bookings_for_sync(set_id):
    conn = get_db_connection()
    bookings_cursor = conn.execute("""
        SELECT meal_date, meal_time, host_name, host_phone, host_email,
               location_type, address, notes, status
        FROM bookings
        WHERE set_id = ? AND status = 'confirmed' AND meal_date >= date('now', '-7 days')
        ORDER BY meal_date ASC
    """, (set_id,))
    
    rows = []
    for b in bookings_cursor.fetchall():
        rows.append({
            "date": b["meal_date"],
            "day_of_week": format_day_of_week(b["meal_date"]),
            "time": b["meal_time"],
            "host_name": b["host_name"],
            "host_phone": b["host_phone"],
            "host_email": b["host_email"] or "",
            "location_type": format_location_label(b["location_type"]),
            "address": b["address"] or "",
            "notes": b["notes"] or "",
            "status": "Confirmed"
        })
    conn.close()
    return rows

def sync_missionary_set_to_sheets(set_id):
    """
    Syncs confirmed bookings for a specific missionary set to Google Sheets.
    Supports either 'webhook' mode (recommended) or 'service_account' mode.
    """
    conn = get_db_connection()
    missionary_set = conn.execute("SELECT * FROM missionary_sets WHERE id = ?", (set_id,)).fetchone()
    
    if not missionary_set:
        conn.close()
        return {"success": False, "message": "Missionary set not found"}

    sync_mode = missionary_set["sync_mode"] or "webhook"
    
    if sync_mode == "disabled":
        conn.close()
        return {"success": True, "message": "Sync is disabled for this companionship"}

    bookings = get_set_bookings_for_sync(set_id)
    
    if sync_mode == "webhook":
        webhook_url = (missionary_set["google_webhook_url"] or "").strip()
        if not webhook_url:
            conn.close()
            return {"success": False, "message": "Google Webhook URL is not configured for this set."}
        
        payload = {
            "action": "sync_all",
            "set_id": set_id,
            "set_name": missionary_set["name"],
            "missionary_phone": missionary_set["phone"],
            "dietary_restrictions": missionary_set["dietary_restrictions"],
            "bookings": bookings
        }
        
        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE missionary_sets SET last_synced_at = ? WHERE id = ?", (now_str, set_id))
                conn.commit()
                conn.close()
                return {"success": True, "message": f"Successfully synced {len(bookings)} bookings to Google Sheet!", "timestamp": now_str}
            else:
                conn.close()
                return {"success": False, "message": f"Webhook returned HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            conn.close()
            logger.exception("Error syncing via webhook")
            return {"success": False, "message": f"Webhook connection error: {str(e)}"}

    elif sync_mode == "service_account":
        from app.config import Config
        sheet_id = (missionary_set["google_sheet_id"] or "").strip()
        tab_name = (missionary_set["google_sheet_tab"] or "").strip() or "Dinners"
        sa_file = Config.GOOGLE_SERVICE_ACCOUNT_FILE

        if not sa_file or not sheet_id:
            conn.close()
            return {"success": False, "message": "Google Service Account credentials file or Sheet ID not set."}

        try:
            import gspread
            gc = gspread.service_account(filename=sa_file)
            sh = gc.open_by_key(sheet_id)
            try:
                ws = sh.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=tab_name, rows="100", cols="10")

            # Prepare data table
            headers = ["Date", "Day", "Time", "Host Name", "Phone Number", "Location / Type", "Address", "Notes", "Status"]
            table_rows = [headers]
            for b in bookings:
                table_rows.append([
                    b["date"],
                    b["day_of_week"],
                    b["time"],
                    b["host_name"],
                    b["host_phone"],
                    b["location_type"],
                    b["address"],
                    b["notes"],
                    b["status"]
                ])
            
            ws.clear()
            ws.update("A1", table_rows)
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE missionary_sets SET last_synced_at = ? WHERE id = ?", (now_str, set_id))
            conn.commit()
            conn.close()
            return {"success": True, "message": f"Successfully updated Google Sheet tab '{tab_name}' with {len(bookings)} entries.", "timestamp": now_str}
        except Exception as e:
            conn.close()
            logger.exception("Error syncing via Google Service Account")
            return {"success": False, "message": f"Service account sync error: {str(e)}"}

    conn.close()
    return {"success": False, "message": f"Unknown sync mode: {sync_mode}"}
