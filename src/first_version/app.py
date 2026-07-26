import json
import math
import os
import pandas as pd
import streamlit as st

CONFIG_FILE = "vhs_config.json"

st.set_page_config(
    page_title="Berlin VHS Explorer",
    page_icon="🧘",
    layout="wide"
)

# Custom CSS Styling
st.markdown("""
    <style>
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 4px;
        margin-bottom: 6px;
        background-color: #f0f2f6;
        color: #31333F;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🧘 Berlin VHS Course Explorer")
st.caption("A fast, custom explorer tailored for the official Berlin Volkshochschule Open Data feed.")

@st.cache_data
def load_and_parse_data():
    try:
        with open("vhs_courses.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        events = raw_data.get("veranstaltungen", {}).get("veranstaltung", [])
        if isinstance(events, dict):
            events = [events]

        parsed = []
        for e in events:
            # 1. Safe extraction of text description
            desc = ""
            texts = e.get("text", [])
            if isinstance(texts, list):
                for t in texts:
                    if t.get("eigenschaft") == "Beschreibung":
                        desc = t.get("text") or ""
            elif isinstance(texts, dict):
                desc = texts.get("text") or ""

            # 2. Extract Tags
            tags = e.get("schlagwort", [])
            if isinstance(tags, str):
                tags = [tags]

            # 3. Extract Location
            addresses = e.get("ortetermine", {}).get("adresse", [])
            addr_str = "N/A"
            if isinstance(addresses, list) and len(addresses) > 0:
                first_addr = addresses[0]
                addr_str = f"{first_addr.get('strasse', '')}, {first_addr.get('plz', '')} {first_addr.get('ort', '')} ({first_addr.get('raum', '')})".strip(" ,()")
            elif isinstance(addresses, dict):
                addr_str = f"{addresses.get('strasse', '')}, {addresses.get('plz', '')} {addresses.get('ort', '')}".strip(" ,")

            # 4. Extract Instructor
            dozent = e.get("dozent", {})
            dozent_name = "N/A"
            if isinstance(dozent, dict) and dozent.get("name"):
                dozent_name = f"{dozent.get('anrede', '')} {dozent.get('vorname', '')} {dozent.get('name', '')}".strip()

            # 5. Price Numeric Conversion (handles German commas, e.g. "24,50")
            raw_price = e.get("preis", {}).get("betrag", "0")
            try:
                numeric_price = float(str(raw_price).replace(",", "."))
            except (ValueError, TypeError):
                numeric_price = 0.0

            # 6. Seat availability
            cur_participants = int(e.get("aktuelle_teilnehmerzahl") or 0)
            max_participants = int(e.get("maximale_teilnehmerzahl") or 0)
            available_seats = max_participants - cur_participants if max_participants > 0 else 0

            # 7. Dates
            beginn_dt = pd.to_datetime(e.get("beginn_datum"), errors="coerce")

            parsed.append({
                "guid": e.get("guid") or e.get("nummer"),
                "nummer": e.get("nummer"),
                "name": e.get("name", "Unbekannter Kurs"),
                "bezirk": e.get("bezirk", "Berlin"),
                "art": e.get("veranstaltungsart", "Kurs"),
                "beginn": e.get("beginn_datum", ""),
                "beginn_dt": beginn_dt,
                "ende": e.get("ende_datum", ""),
                "anzahl_termine": e.get("anzahl_termine", ""),
                "preis": raw_price,
                "numeric_price": numeric_price,
                "preis_zusatz": e.get("preis", {}).get("zusatz", ""),
                "cur_seats": cur_participants,
                "max_seats": max_participants,
                "available_seats": available_seats,
                "tags": tags,
                "description": desc,
                "location": addr_str if addr_str else "N/A",
                "dozent": dozent_name,
                "url": e.get("webadresse", {}).get("uri", ""),
            })

        return pd.DataFrame(parsed)
    except FileNotFoundError:
        st.error("⚠️ File `vhs_courses.json` not found in current directory.")
        return pd.DataFrame()

df = load_and_parse_data()

# --- Config & Session State Management ---
def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_settings(settings_dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
        st.sidebar.success("✅ Settings & bookmarks saved!")
    except Exception as err:
        st.sidebar.error(f"Failed to save settings: {err}")

saved_config = load_settings()

if "marked_guids" not in st.session_state:
    st.session_state.marked_guids = set(saved_config.get("marked_guids", []))

def toggle_mark_course(guid):
    if guid in st.session_state.marked_guids:
        st.session_state.marked_guids.remove(guid)
    else:
        st.session_state.marked_guids.add(guid)

def export_dataframe_buttons(dataframe, key_prefix):
    """Helper component to export clean CSV and JSON data."""
    if dataframe.empty:
        return

    # Prepare export-ready DataFrame (drop helper/internal datetime columns)
    export_df = dataframe.drop(columns=["beginn_dt"], errors="ignore").copy()

    col_csv, col_json = st.columns(2)
    with col_csv:
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export CSV",
            data=csv_data,
            file_name=f"{key_prefix}_vhs_courses.csv",
            mime="text/csv",
            key=f"csv_{key_prefix}"
        )
    with col_json:
        json_data = export_df.to_json(orient="records", force_ascii=False, indent=2)
        st.download_button(
            label="📥 Export JSON",
            data=json_data,
            file_name=f"{key_prefix}_vhs_courses.json",
            mime="application/json",
            key=f"json_{key_prefix}"
        )

if not df.empty:
    # --- Sidebar Controls ---
    st.sidebar.header("🎯 Filters & Controls")

    # 1. District Filter
    districts = sorted([d for d in df["bezirk"].dropna().unique() if d])
    default_districts = saved_config.get("selected_districts", [])
    selected_districts = st.sidebar.multiselect("District (Bezirk)", districts, default=[d for d in default_districts if d in districts])

    # 2. Title Exclude Filter
    st.sidebar.subheader("🚫 Exclude Titles")
    default_exclude = saved_config.get("exclude_text", "Integrationskurs")
    exclude_text = st.sidebar.text_input(
        "Exclude courses containing keywords (comma-separated):",
        value=default_exclude,
        help="Separate keywords by commas to hide multiple terms (e.g. Integrationskurs, Deutsch, B1)"
    )

    # 3. Free Seats Filter
    default_seats = saved_config.get("only_available", False)
    only_available = st.sidebar.checkbox("Only show courses with free seats", value=default_seats)

    # 4. Active Date Range Filter
    st.sidebar.subheader("Course Start Date")
    valid_dates = df["beginn_dt"].dropna()
    if not valid_dates.empty:
        min_dt, max_dt = valid_dates.min().date(), valid_dates.max().date()
        date_range = st.sidebar.date_input("Filter start date within:", value=(min_dt, max_dt), min_value=min_dt, max_value=max_dt)
    else:
        date_range = None

    # 5. Display & Pagination Controls
    st.sidebar.subheader("Display & Pagination")
    sort_options = ["Start Date (Soonest)", "Price (Low to High)", "Price (High to Low)", "Seats Available"]
    default_sort_idx = sort_options.index(saved_config.get("sort_by", "Start Date (Soonest)")) if saved_config.get("sort_by") in sort_options else 0
    sort_by = st.sidebar.selectbox("Sort results by", sort_options, index=default_sort_idx)

    page_size_options = [50, 100, 250, 500, 1000, 2000]
    default_size_idx = page_size_options.index(saved_config.get("page_size", 50)) if saved_config.get("page_size") in page_size_options else 0
    page_size = st.sidebar.selectbox("Items per page", page_size_options, index=default_size_idx)

    # Save Settings & Bookmarks Button
    if st.sidebar.button("💾 Save Settings & Bookmarks"):
        settings_to_save = {
            "selected_districts": selected_districts,
            "exclude_text": exclude_text,
            "only_available": only_available,
            "sort_by": sort_by,
            "page_size": page_size,
            "marked_guids": list(st.session_state.marked_guids)
        }
        save_settings(settings_to_save)

    # --- Filter Pipeline Execution ---
    filtered_df = df.copy()

    if selected_districts:
        filtered_df = filtered_df[filtered_df["bezirk"].isin(selected_districts)]

    if exclude_text:
        exclude_terms = [term.strip().lower() for term in exclude_text.split(",") if term.strip()]
        for term in exclude_terms:
            filtered_df = filtered_df[~filtered_df["name"].str.lower().str.contains(term, na=False)]

    if only_available:
        filtered_df = filtered_df[filtered_df["available_seats"] > 0]

    if date_range and len(date_range) == 2:
        start_filter, end_filter = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered_df = filtered_df[(filtered_df["beginn_dt"] >= start_filter) & (filtered_df["beginn_dt"] <= end_filter)]

    # --- Search Input ---
    search_query = st.text_input("🔍 Search by title, keyword, or course number (e.g., Qi Gong, FK3.111, Yoga)...", "")

    if search_query:
        query = search_query.lower()
        mask = (
                filtered_df["name"].str.lower().str.contains(query, na=False) |
                filtered_df["nummer"].str.lower().str.contains(query, na=False) |
                filtered_df["description"].str.lower().str.contains(query, na=False) |
                filtered_df["tags"].apply(lambda tags: any(query in t.lower() for t in tags) if isinstance(tags, list) else False)
        )
        filtered_df = filtered_df[mask]

    # --- Sorting Logic ---
    if sort_by == "Start Date (Soonest)":
        filtered_df = filtered_df.sort_values(by="beginn_dt", ascending=True)
    elif sort_by == "Price (Low to High)":
        filtered_df = filtered_df.sort_values(by="numeric_price", ascending=True)
    elif sort_by == "Price (High to Low)":
        filtered_df = filtered_df.sort_values(by="numeric_price", ascending=False)
    elif sort_by == "Seats Available":
        filtered_df = filtered_df.sort_values(by="available_seats", ascending=False)

    # Metrics Summary Bar
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Courses Found", len(filtered_df))
    m2.metric("Districts Represented", filtered_df["bezirk"].nunique())
    m3.metric("Courses with Free Seats", len(filtered_df[filtered_df["available_seats"] > 0]))
    m4.metric("Marked Favorites 🔖", len(st.session_state.marked_guids))
    st.markdown("---")

    # --- Main Navigation Tabs ---
    tab_all, tab_marked = st.tabs(["📋 All Courses", f"⭐ Marked Courses ({len(st.session_state.marked_guids)})"])

    # --- Render Card Helper Function ---
    def render_course_card(row, is_marked_view=False):
        guid = row["guid"]
        is_marked = guid in st.session_state.marked_guids
        badge = "⭐ " if is_marked else "📍 "

        seats_status = (
            f"🔴 Full ({row['cur_seats']}/{row['max_seats']})"
            if row['available_seats'] <= 0
            else f"🟢 {row['available_seats']} seats left ({row['cur_seats']}/{row['max_seats']} booked)"
        )

        with st.expander(f"{badge}[{row['nummer']}] {row['name']} — {row['bezirk']} ({row['preis']} €)"):
            if row['tags']:
                tag_html = " ".join([f"<span class='badge'>#{t}</span>" for t in row['tags']])
                st.markdown(tag_html, unsafe_allow_html=True)

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("**Description:**")
                st.markdown(f">{row['description']}" if row['description'] else "_No description available._")
                st.markdown(f"**Location:** {row['location']}")
                st.markdown(f"**Instructor:** {row['dozent']}")

            with col2:
                st.info(f"**Price:** {row['preis']} €\n\n_{row['preis_zusatz']}_")
                st.write(f"**Schedule:** {row['beginn']} to {row['ende']} ({row['anzahl_termine']} sessions)")
                st.write(f"**Availability:** {seats_status}")

                # Bookmark Action Button
                btn_label = "❌ Remove Bookmark" if is_marked else "⭐ Bookmark Course"
                st.button(btn_label, key=f"mark_{'fav_' if is_marked_view else ''}{guid}", on_click=toggle_mark_course, args=(guid,))

                if row['url']:
                    st.link_button("Book on Official VHS Site 🔗", row['url'], type="primary")

    # --- TAB 1: ALL COURSES ---
    with tab_all:
        st.subheader("Filter & Export Results")
        export_dataframe_buttons(filtered_df, "filtered")
        st.markdown("---")

        total_items = len(filtered_df)
        total_pages = max(1, math.ceil(total_items / page_size))

        col_page, col_info = st.columns([1, 3])
        with col_page:
            current_page = st.number_input(f"Page (1 of {total_pages})", min_value=1, max_value=total_pages, value=1, step=1)
        with col_info:
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            st.write("")
            st.write(f"Showing **{start_idx + 1 if total_items > 0 else 0}** - **{end_idx}** of **{total_items}** results")

        paginated_df = filtered_df.iloc[start_idx:end_idx]

        for _, row in paginated_df.iterrows():
            render_course_card(row, is_marked_view=False)

    # --- TAB 2: MARKED COURSES ---
    with tab_marked:
        marked_df = df[df["guid"].isin(st.session_state.marked_guids)]

        st.subheader("⭐ Your Marked Favorites")

        if not marked_df.empty:
            export_dataframe_buttons(marked_df, "marked")
            st.markdown("---")

            for _, row in marked_df.iterrows():
                render_course_card(row, is_marked_view=True)
        else:
            st.info("No courses marked yet. Click '⭐ Bookmark Course' inside any course card to build your list.")