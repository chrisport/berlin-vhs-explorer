import json
import sqlite3
import pandas as pd
import urllib.request
import os

FEED_URL = "https://www.vhsit.berlin.de/VHSKURSE/OpenData/Kurse.json" # Adjust to exact feed URL
DB_FILE = "vhs_courses.db"
JSON_TEMP = "temp_vhs.json"

def fetch_data():
    print("📥 Downloading latest VHS Open Data feed...")
    # Stream download to avoid loading huge raw string in RAM
    urllib.request.urlretrieve(FEED_URL, JSON_TEMP)

def process_and_build_sqlite():
    print("⚡ Parsing data into SQLite...")
    with open(JSON_TEMP, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    events = raw_data.get("veranstaltungen", {}).get("veranstaltung", [])
    if isinstance(events, dict):
        events = [events]

    parsed = []
    for e in events:
        desc = ""
        texts = e.get("text", [])
        if isinstance(texts, list):
            for t in texts:
                if t.get("eigenschaft") == "Beschreibung":
                    desc = t.get("text") or ""
        elif isinstance(texts, dict):
            desc = texts.get("text") or ""

        tags = e.get("schlagwort", [])
        if isinstance(tags, str):
            tags = [tags]
        tags_str = ", ".join(tags)

        addresses = e.get("ortetermine", {}).get("adresse", [])
        addr_str = "N/A"
        if isinstance(addresses, list) and len(addresses) > 0:
            first = addresses[0]
            addr_str = f"{first.get('strasse', '')}, {first.get('plz', '')} {first.get('ort', '')}".strip(" ,")
        elif isinstance(addresses, dict):
            addr_str = f"{addresses.get('strasse', '')}, {addresses.get('plz', '')} {addresses.get('ort', '')}".strip(" ,")

        dozent = e.get("dozent", {})
        dozent_name = "N/A"
        if isinstance(dozent, dict) and dozent.get("name"):
            dozent_name = f"{dozent.get('anrede', '')} {dozent.get('vorname', '')} {dozent.get('name', '')}".strip()

        raw_price = e.get("preis", {}).get("betrag", "0")
        try:
            numeric_price = float(str(raw_price).replace(",", "."))
        except (ValueError, TypeError):
            numeric_price = 0.0

        cur_participants = int(e.get("aktuelle_teilnehmerzahl") or 0)
        max_participants = int(e.get("maximale_teilnehmerzahl") or 0)
        available_seats = max_participants - cur_participants if max_participants > 0 else 0

        parsed.append((
            str(e.get("guid") or e.get("nummer")),
            e.get("nummer", ""),
            e.get("name", "Unbekannter Kurs"),
            e.get("bezirk", "Berlin"),
            e.get("veranstaltungsart", "Kurs"),
            e.get("beginn_datum", ""),
            e.get("ende_datum", ""),
            numeric_price,
            raw_price,
            available_seats,
            cur_participants,
            max_participants,
            tags_str,
            desc,
            addr_str,
            dozent_name,
            e.get("webadresse", {}).get("uri", "")
        ))

    # Remove existing DB
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE courses (
            guid TEXT PRIMARY KEY,
            nummer TEXT,
            name TEXT,
            bezirk TEXT,
            art TEXT,
            beginn TEXT,
            ende TEXT,
            numeric_price REAL,
            raw_price TEXT,
            available_seats INTEGER,
            cur_seats INTEGER,
            max_seats INTEGER,
            tags TEXT,
            description TEXT,
            location TEXT,
            dozent TEXT,
            url TEXT
        )
    """)

    cursor.executemany("""
        INSERT INTO courses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, parsed)

    # 🚀 Create indexes for fast in-browser SQL filtering
    print("📌 Creating database indexes...")
    cursor.execute("CREATE INDEX idx_bezirk ON courses(bezirk);")
    cursor.execute("CREATE INDEX idx_price ON courses(numeric_price);")
    cursor.execute("CREATE INDEX idx_beginn ON courses(beginn);")
    cursor.execute("CREATE INDEX idx_seats ON courses(available_seats);")

    conn.commit()
    conn.close()

    # Clean temporary JSON
    if os.path.exists(JSON_TEMP):
        os.remove(JSON_TEMP)
    print(f"✅ Finished! Database created at {DB_FILE} ({round(os.path.getsize(DB_FILE)/(1024*1024), 2)} MB)")

if __name__ == "__main__":
    fetch_data()
    process_and_build_sqlite()