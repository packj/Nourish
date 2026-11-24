import sqlite3
import os
from datetime import datetime
from app.config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS missionary_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        phone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        default_time TEXT DEFAULT '5:00 PM',
        dietary_restrictions TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        sync_mode TEXT DEFAULT 'webhook',
        google_webhook_url TEXT DEFAULT '',
        google_sheet_id TEXT DEFAULT '',
        google_sheet_tab TEXT DEFAULT '',
        last_synced_at TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id INTEGER NOT NULL,
        meal_date TEXT NOT NULL,
        meal_time TEXT DEFAULT '5:00 PM',
        host_name TEXT NOT NULL,
        host_phone TEXT NOT NULL,
        host_email TEXT DEFAULT '',
        location_type TEXT DEFAULT 'home',
        address TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        cancel_code TEXT NOT NULL,
        status TEXT DEFAULT 'confirmed',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (set_id) REFERENCES missionary_sets(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(set_id, meal_date, status);

    CREATE TABLE IF NOT EXISTS blackout_dates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id INTEGER NOT NULL,
        blocked_date TEXT NOT NULL,
        reason TEXT DEFAULT 'Unavailable',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        UNIQUE(set_id, blocked_date),
        FOREIGN KEY (set_id) REFERENCES missionary_sets(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    ''')

    # Seed initial missionary sets if none exist
    cursor.execute("SELECT COUNT(*) FROM missionary_sets")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO missionary_sets (name, slug, phone, default_time, dietary_restrictions, notes, sync_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Ward Elders",
            "elders",
            "555-0100",
            "5:00 PM",
            "No known allergies. Happy to eat anything!",
            "We love to share a short 10-15 minute spiritual message. Please let us know if any friends or neighbors will be joining!",
            "webhook"
        ))
        cursor.execute('''
            INSERT INTO missionary_sets (name, slug, phone, default_time, dietary_restrictions, notes, sync_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Sister Missionaries",
            "sisters",
            "555-0101",
            "5:30 PM",
            "Sister Smith is lactose intolerant. Sister Johnson prefers mild foods.",
            "We would love to share a scripture or musical thought. Thank you for opening your home!",
            "webhook"
        ))

    conn.commit()
    conn.close()
