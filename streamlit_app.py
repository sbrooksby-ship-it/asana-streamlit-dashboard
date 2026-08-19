import hmac
import os
import io
import csv
import json
import psycopg2
import requests
import pandas as pd
import streamlit as st
from asana_sync import main as run_sync

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ticket desk", layout="wide")

# --- CUSTOM STYLING ---
st.markdown("""
<style>
    .stApp {
        background-color: #f5f3ee;
        color: #2b2b2b;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    [data-testid="stSidebar"] {
        background-color: #ede9e1;
        padding-top: 1rem;
    }
    
    [data-testid="stForm"] {
        background-color: #ffffff !important;
        border: 1px solid #d3d3d3 !important;
        border-radius: 8px !important;
        padding: 2rem !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        max-width: 600px; 
    }
    
    /* --- FORCE ALL SELECTBOXES & DROPDOWNS TO PURE WHITE --- */
    [data-testid="stSelectbox"],
    [data-testid="stSelectbox"] > div,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] * {
        background-color: #ffffff !important;
        background: #ffffff !important;
        color: #111111 !important;
    }
    
    /* Input & Select Borders */
    .stTextInput div[data-baseweb="base-input"],
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div {
        border: 1px solid #b0b0b0 !important;
        border-radius: 4px !important;
    }
    
    .stTextInput input, .stSelectbox span {
        color: #111111 !important;
    }
    
    .sub-header {
        color: #e06d53;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 0px;
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        color: #1a1a1a;
        margin-top: -5px;
        margin-bottom: 0px;
        line-height: 1.1;
    }
    
    .main-tagline {
        color: #666;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-container {
        display: flex;
        gap: 0px;
        background-color: #ffffff;
        border: 1px solid #e2ded5;
        border-radius: 4px;
        margin-bottom: 2rem;
        overflow: hidden;
    }
    
    .metric-box {
        flex: 1;
        padding: 12px 20px;
        border-right: 1px solid #e2ded5;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-box:last-child {
        border-right: none;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #777;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1a1a1a;
    }
    
    .ticket-card {
        background: #ffffff;
        border: 1px solid #e2ded5;
        border-radius: 4px;
        padding: 18px 22px;
        margin-bottom: 4px;
        position: relative;
    }
    
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-category {
        background-color: #d1e7dd;
        color: #0f5132;
    }
    .badge-section {
        background-color: #cfe2ff;
        color: #084298;
    }
    .badge-status {
        background-color: #e2e3e5;
        color: #41464b;
    }
    
    .ticket-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #111;
        margin: 8px 0px 6px 0px;
    }
    
    .ticket-desc {
        color: #666;
        font-size: 0.88rem;
        line-height: 1.4;
        margin-bottom: 12px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .ticket-assignee {
        font-size: 0.8rem;
        color: #888;
    }
    
    .dot-indicator {
        height: 10px;
        width: 10px;
        background-color: #e06d53;
        border-radius: 50%;
        display: inline-block;
        margin-right: 10px;
    }
    
    .cat-bar-container {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
    }
    .cat-bar-label {
        width: 180px;
        font-size: 0.85rem;
        color: #555;
    }
    .cat-bar-track {
        flex-grow: 1;
        height: 10px;
        background-color: #e9ecef;
        margin: 0 15px;
        border-radius: 2px;
        overflow: hidden;
    }
    .cat-bar-fill {
        height: 100%;
        background-color: #e06d53;
    }
    .cat-bar-count {
        font-weight: 700;
        font-size: 0.9rem;
        width: 30px;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)


# --- AUTHENTICATION ---
def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["username"], st.secrets.get("AUTH_USERNAME", "admin")) and \
           hmac.compare_digest(st.session_state["password"], st.secrets.get("AUTH_PASSWORD", "admin")):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<p class='sub-header'>ASANA / DIVISION 5</p>", unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>Ticket desk</h1>", unsafe_allow_html=True)
    st.write("Please sign in to access the dashboard.")
    
    with st.form("login_form"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.form_submit_button("Sign in", on_click=password_entered)

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Invalid username or password")
    return False

if not check_password():
    st.stop()


# --- DATABASE & ASANA API LOGIC ---
def get_db_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

@st.cache_data(ttl=600)
def fetch_asana_sections():
    token = st.secrets["ASANA_TOKEN"]
    project_gid = st.secrets["PROJECT_GID"]
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"https://app.asana.com/api/1.0/projects/{project_gid}/sections", headers=headers)
    response.raise_for_status()
    data = response.json().get("data", [])
    return {sec["name"]: sec["gid"] for sec in data}

def move_task_to_section_in_asana(task_gid, section_gid, section_name):
    token = st.secrets["ASANA_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {"data": {"task": task_gid}}
    response = requests.post(f"https://app.asana.com/api/1.0/sections/{section_gid}/addTask", json=body, headers=headers)
    response.raise_for_status()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE tasks SET section_gid = %s, section_name = %s, modified_at = NOW() WHERE gid = %s", (section_gid, section_name, task_gid))
            history_details = json.dumps({"fields": ["section"], "new_section": section_name})
            cur.execute("INSERT INTO task_history (task_gid, change_type, details) VALUES (%s, 'updated', %s::jsonb)", (task_gid, history_details))
        conn.commit()
    finally:
        conn.close()

def toggle_task_status_in_asana(gid, current_status):
    new_status = not current_status
    token = st.secrets["ASANA_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"data": {"completed": new_status}}
    response = requests.put(f"https://app.asana.com/api/1.0/tasks/{gid}", json=data, headers=headers)
    response.raise_for_status()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE tasks SET completed = %s, modified_at = NOW() WHERE gid = %s", (new_status, gid))
            history_details = json.dumps({"fields": ["completed"]})
            cur.execute("INSERT INTO task_history (task_gid, change_type, details) VALUES (%s, 'updated', %s::jsonb)", (gid, history_details))
        conn.commit()
    finally:
        conn.close()

def query_dashboard(category, status, assignee, overdue, search, section):
    conn = get_db_connection()
    try:
        conditions = []
        values = []

        if category and category != "All":
            conditions.append("category = %s")
            values.append(category)

        if section and section != "All":
            conditions.append("section_name = %s")
            values.append(section)

        if status == "Open":
            conditions.append("completed = FALSE AND active = TRUE")
        elif status == "Completed":
            conditions.append("completed = TRUE")
        elif status == "Removed":
            conditions.append("active = FALSE")
        elif status == "Active":
            conditions.append("active = TRUE")

        if assignee and assignee != "Everyone":
            conditions.append("assignee_name = %s")
            values.append(assignee)

        if overdue:
            conditions.append("completed = FALSE AND active = TRUE AND due_on < CURRENT_DATE")

        if search:
            conditions.append("(name ILIKE %s OR description ILIKE %s OR assignee_name ILIKE %s)")
            values.extend([f"%{search}%"] * 3)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT gid, name, description, category, completed, active, due_on, assignee_name, last_seen_at, asana_url, section_name, section_gid
            FROM tasks {where_clause}
            ORDER BY completed ASC, due_on NULLS LAST, modified_at DESC NULLS LAST, name
        """
        df = pd.read_sql(query, conn, params=values)

        with conn.cursor() as cur:
            cur.execute("SELECT category, COUNT(*) FROM tasks WHERE active = TRUE GROUP BY category ORDER BY COUNT(*) DESC, category")
            categories = cur.fetchall()

            cur.execute("SELECT section_name, COUNT(*) FROM tasks WHERE active = TRUE AND section_name IS NOT NULL GROUP BY section_name ORDER BY section_name")
            sections = cur.fetchall()

            cur.execute("SELECT DISTINCT assignee_name FROM tasks WHERE active = TRUE AND assignee_name IS NOT NULL ORDER BY assignee_name")
            assignees = ["Everyone"] + [row[0] for row in cur.fetchall()]

            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE active), 
                    COUNT(*) FILTER (WHERE active AND NOT completed), 
                    COUNT(*) FILTER (WHERE active AND completed),
                    COUNT(*) FILTER (WHERE active AND NOT completed AND due_on < CURRENT_DATE),
                    COUNT(*) FILTER (WHERE NOT active) 
                FROM tasks
            """)
            stats = cur.fetchone()

            cur.execute("SELECT status, finished_at, task_count, error_message FROM sync_runs ORDER BY id DESC LIMIT 1")
            sync_run = cur.fetchone() or ("never", None, 0, None)

        return df, categories, sections, assignees, stats, sync_run
    finally:
        conn.close()

def fetch_ticket_details(gid):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE gid = %s", (gid,))
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description] if row else []
            task = dict(zip(columns, row)) if row else None

            cur.execute("SELECT changed_at, change_type, details FROM task_history WHERE task_gid = %s ORDER BY changed_at DESC", (gid,))
            history = cur.fetchall()
        return task, history
    finally:
        conn.close()


# --- INTERACTIVE CALLBACKS ---
def handle_quick_move(task_gid, widget_key, current_sec):
    new_sec = st.session_state[widget_key]
    if new_sec != current_sec:
        sections_map = fetch_asana_sections()
        new_gid = sections_map.get(new_sec)
        if new_gid:
            move_task_to_section_in_asana(task_gid, new_gid, new_sec)
            st.toast(f"Moved to {new_sec}")


# --- SIDEBAR / FILTERS ---
st.sidebar.markdown("<p style='color:#e06d53; font-weight:700; font-size:0.75rem; letter-spacing:1px;'>ORGANIZE</p>", unsafe_allow_html=True)

search_query = st.sidebar.text_input("Find a ticket", placeholder="Name, detail, person...", label_visibility="visible")
status_filter = st.sidebar.selectbox("Status", ["All tickets", "Open", "Completed", "Active", "Removed"], index=1)

_df, cat_list, sec_list, assign_options, stats, sync_run = query_dashboard("", "All tickets", "Everyone", False, "", "All")

sec_options = ["All"] + [s[0] for s in sec_list if s[0]]
section_filter = st.sidebar.selectbox("Department / Section", sec_options)

assignee_filter = st.sidebar.selectbox("Assignee", assign_options)
overdue_filter = st.sidebar.checkbox("Overdue only", value=False)

cat_options = ["All"] + [c[0] for c in cat_list]
category_filter = st.sidebar.selectbox("Category Filter", cat_options)

st.sidebar.markdown("<br><p style='color:#e06d53; font-weight:700; font-size:0.75rem; letter-spacing:1px;'>CATEGORIES</p>", unsafe_allow_html=True)
for cat_name, count in cat_list:
    st.sidebar.markdown(f"<div style='display:flex; justify-content:space-between; font-size:0.85rem; color:#444; margin-bottom:4px;'><span>{cat_name}</span><span style='font-weight:600;'>{count}</span></div>", unsafe_allow_html=True)


# --- MAIN HEADER ---
col_head, col_logout = st.columns([4, 1])
with col_head:
    st.markdown("<p class='sub-header'>ASANA / DIVISION 5</p>", unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>Ticket desk</h1>", unsafe_allow_html=True)
    st.markdown("<p class='main-tagline'>A focused view of what needs attention, grouped by what each ticket is for.</p>", unsafe_allow_html=True)

with col_logout:
    st.markdown(f"<p style='text-align:right; font-size:0.85rem; color:#777;'>{stats[0]} active tickets</p>", unsafe_allow_html=True)
    if st.button("Sign out"):
        st.session_state["password_correct"] = False
        st.rerun()


# --- METRICS BANNER ---
st.markdown(f"""
<div class="metric-container">
    <div class="metric-box"><span class="metric-label">Total</span><span class="metric-value">{stats[0]}</span></div>
    <div class="metric-box"><span class="metric-label">Open</span><span class="metric-value">{stats[1]}</span></div>
    <div class="metric-box"><span class="metric-label">Completed</span><span class="metric-value">{stats[2]}</span></div>
    <div class="metric-box"><span class="metric-label">Overdue</span><span class="metric-value">{stats[3]}</span></div>
    <div class="metric-box"><span class="metric-label">Archived</span><span class="metric-value">{stats[4]}</span></div>
</div>
""", unsafe_allow_html=True)


# --- DATA FETCH ---
df, _, _, _, _, sync_run = query_dashboard(category_filter, status_filter, assignee_filter, overdue_filter, search_query, section_filter)


# --- WORK QUEUE HEADER ---
col_q1, col_q2 = st.columns([3, 1])
with col_q1:
    st.markdown("<p style='color:#e06d53; font-weight:700; font-size:0.75rem; letter-spacing:1px; margin-bottom:0px;'>WORK QUEUE</p>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='font-size:1.6rem; font-weight:800; margin-top:0px; margin-bottom:0px;'>{len(df)} matching tickets</h2>", unsafe_allow_html=True)
    
    last_sync_str = sync_run[1].strftime("%b %d, %Y at %I:%M %p") if sync_run[1] else "Never"
    st.markdown(f"<p style='font-size:0.8rem; color:#888; margin-bottom:15px;'>Last sync: {last_sync_str} · {sync_run[0].title()}</p>", unsafe_allow_html=True)

with col_q2:
    if st.button("🔄 Sync now", type="primary", use_container_width=True):
        with st.spinner("Syncing..."):
            try:
                os.environ["ASANA_TOKEN"] = st.secrets["ASANA_TOKEN"]
                os.environ["PROJECT_GID"] = st.secrets["PROJECT_GID"]
                os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
                run_sync()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed: {e}")

# --- CATEGORY BAR CHART ---
if not df.empty:
    cat_counts = df['category'].value_counts()
    max_val = df['category'].value_counts().max()
    
    st.markdown("<div style='margin-bottom: 25px;'>", unsafe_allow_html=True)
    for cat, count in cat_counts.items():
        width_pct = int((count / max_val) * 100) if max_val > 0 else 0
        st.markdown(f"""
        <div class="cat-bar-container">
            <div class="cat-bar-label">{cat}</div>
            <div class="cat-bar-track">
                <div class="cat-bar-fill" style="width: {width_pct}%;"></div>
            </div>
            <div class="cat-bar-count">{count}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# --- CSV EXPORT ---
if not df.empty:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Category", "Department/Section", "Status", "Assignee", "Due Date", "Description"])
    for _, task in df.iterrows():
        writer.writerow([task["name"], task["category"], task.get("section_name") or "", "Completed" if task["completed"] else "Open", task["assignee_name"] or "Unassigned", task["due_on"] or "", task["description"]])
    
    st.download_button(
        label="Export CSV ↓",
        data=output.getvalue(),
        file_name="ticket-export.csv",
        mime="text/csv",
    )

st.divider()


# --- TICKET MODAL / DIALOG VIEW ---
@st.dialog("Ticket Details")
def show_ticket_modal(gid):
    task, history = fetch_ticket_details(gid)
    if not task:
        st.error("Ticket not found.")
        return
    
    st.markdown(f"### {task.get('name')}")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Category:** {task.get('category')}")
        st.markdown(f"**Department:** {task.get('section_name') or 'None'}")
        st.markdown(f"**Assignee:** {task.get('assignee_name') or 'Unassigned'}")
    with col_b:
        st.markdown(f"**Status:** {'Completed' if task.get('completed') else 'Open'}")
        st.markdown(f"**Due Date:** {task.get('due_on') or 'None'}")
    
    st.markdown("---")
    st.markdown("**Description:**")
    st.write(task.get("description") or "*No description provided.*")
    
    if task.get("asana_url"):
        st.markdown(f"[View in Asana]({task.get('asana_url')})")
        
    st.markdown("---")
    st.markdown("**Actions:**")
    
    try:
        sections_map = fetch_asana_sections()
        section_names = list(sections_map.keys())
        current_sec = task.get("section_name")
        default_index = section_names.index(current_sec) if current_sec in section_names else 0
        
        selected_sec = st.selectbox("Move to Department / Column:", section_names, index=default_index)
        if selected_sec != current_sec:
            if st.button("Confirm Move"):
                with st.spinner("Moving task in Asana..."):
                    try:
                        new_gid = sections_map[selected_sec]
                        move_task_to_section_in_asana(gid, new_gid, selected_sec)
                        st.success(f"Moved to {selected_sec}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to move: {e}")
    except Exception as e:
        st.caption(f"Could not load departments: {e}")

    is_completed = task.get("completed", False)
    btn_label = "✅ Mark as Completed" if not is_completed else "↩️ Reopen Ticket"
    
    if st.button(btn_label, type="primary"):
        with st.spinner("Updating Asana..."):
            try:
                toggle_task_status_in_asana(gid, is_completed)
                st.success("Ticket status updated!")
                st.rerun() 
            except Exception as e:
                st.error(f"Failed to update Asana: {e}")
                
    st.markdown("---")
    st.markdown("**History Log:**")
    if history:
        for changed_at, change_type, details in history:
            st.caption(f"• **{change_type.title()}** on {changed_at.strftime('%Y-%m-%d %H:%M')} — {details}")
    else:
        st.caption("No history recorded.")


# --- DISPLAY TICKET CARDS ---
def render_tickets(dataframe):
    try:
        sections_map = fetch_asana_sections()
        section_names = list(sections_map.keys())
    except Exception:
        section_names = []

    for idx, row in dataframe.iterrows():
        status_text = "Completed" if row["completed"] else "Open"
        current_sec = row.get("section_name") or "No Dept"
        
        with st.container():
            st.markdown(f"""
            <div class="ticket-card">
                <div>
                    <span class="dot-indicator"></span>
                    <span class="badge badge-section">{current_sec}</span>
                    <span class="badge badge-category">{row['category']}</span>
                    <span class="badge badge-status">{status_text}</span>
                </div>
                <div class="ticket-title">{row['name']}</div>
                <div class="ticket-desc">{row['description']}</div>
                <div class="ticket-assignee">{row['assignee_name'] or 'Unassigned'}</div>
            </div>
            """, unsafe_allow_html=True)
            
            col_btn1, col_btn2, col_dd, col_blank = st.columns([1.5, 2, 3, 5.5])
            
            with col_btn1:
                if st.button("🔍 View Details", key=f"btn_{row['gid']}", type="tertiary"):
                    show_ticket_modal(row['gid'])
            
            with col_btn2:
                quick_btn_label = "↩️ Reopen" if row["completed"] else "✅ Complete"
                if st.button(quick_btn_label, key=f"btn_quick_{row['gid']}", type="tertiary"):
                    with st.spinner("Updating..."):
                        try:
                            toggle_task_status_in_asana(row['gid'], row["completed"])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update Asana: {e}")
                            
            with col_dd:
                if section_names:
                    default_index = section_names.index(current_sec) if current_sec in section_names else 0
                    widget_key = f"sec_dd_{row['gid']}"
                    
                    st.selectbox(
                        "Move Dept:",
                        options=section_names,
                        index=default_index,
                        key=widget_key,
                        on_change=handle_quick_move,
                        args=(row['gid'], widget_key, current_sec),
                        label_visibility="collapsed"
                    )
            
            st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

if df.empty:
    st.info("No tickets found matching your filters.")
else:
    if status_filter == "All tickets":
        open_df = df[~df['completed']]
        closed_df = df[df['completed']]
        
        if not open_df.empty:
            render_tickets(open_df)
            
        if not closed_df.empty:
            st.markdown("<h3 style='color: #e06d53; margin-top: 2rem;'>Closed Tickets</h3>", unsafe_allow_html=True)
            st.divider()
            render_tickets(closed_df)
    else:
        render_tickets(df)
