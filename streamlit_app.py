import hmac
import os
import io
import csv
import json
import math
import psycopg2
import requests
import pandas as pd
import streamlit as st
from asana_sync import main as run_sync

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ticket desk", layout="wide")

# --- COLOR PALETTE SYSTEM ---
CATEGORY_PALETTE = [
    {"bar": "#6b8e72", "bg": "#eaf2eb", "text": "#2d4a32"},
    {"bar": "#5b7b9a", "bg": "#e8f0f8", "text": "#1f3d5c"},
    {"bar": "#d99b38", "bg": "#fdf5e6", "text": "#7a5210"},
    {"bar": "#b85b75", "bg": "#f9eef2", "text": "#6b2135"},
    {"bar": "#4a969b", "bg": "#e6f4f5", "text": "#1d4e52"},
    {"bar": "#8a7b6b", "bg": "#f2eee9", "text": "#473d32"},
]

def get_category_colors(cat_name: str) -> dict:
    if cat_name == "Continuous Improvement":
        return {"bar": "#e06d53", "bg": "#fbebe8", "text": "#b33a1f"}
    idx = abs(hash(cat_name)) % len(CATEGORY_PALETTE)
    return CATEGORY_PALETTE[idx]


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
    
    /* --- SLIM DOWN DROPDOWNS & INPUTS --- */
    div[data-baseweb="select"] > div,
    .stTextInput div[data-baseweb="base-input"],
    div[data-baseweb="input"] {
        min-height: 34px !important; 
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        border: 1px solid #d0d0d0 !important;
        border-radius: 4px !important;
    }
    
    /* Adjust font size inside dropdowns for elegance */
    div[data-baseweb="select"] * {
        font-size: 0.9rem !important;
    }
    
    /* Force inputs to white */
    [data-testid="stSelectbox"],
    [data-testid="stSelectbox"] > div,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] div {
        background-color: #ffffff !important;
        background: #ffffff !important;
        color: #111111 !important;
    }
    
    .stTextInput input, .stSelectbox span, .stTextArea textarea {
        color: #111111 !important;
        background-color: #ffffff !important;
        font-size: 0.9rem !important;
    }
    
    /* --- TYPOGRAPHY --- */
    .sub-header { color: #e06d53; font-size: 0.8rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 0px; }
    .main-title { font-size: 3rem; font-weight: 800; color: #1a1a1a; margin-top: -5px; margin-bottom: 0px; line-height: 1.1; }
    .main-tagline { color: #666; font-size: 0.95rem; margin-bottom: 1.5rem; }
    
    /* --- MODERN FLOATING CARDS --- */
    .metric-container { 
        display: flex; 
        background-color: #ffffff; 
        border: none !important; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
        border-radius: 6px; 
        margin-bottom: 2rem; 
    }
    .metric-box { flex: 1; padding: 16px 20px; border-right: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center; }
    .metric-box:last-child { border-right: none; }
    .metric-label { font-size: 0.85rem; color: #777; }
    .metric-value { font-size: 1.5rem; font-weight: 800; color: #1a1a1a; }
    
    .ticket-card { 
        background: #ffffff; 
        border: none !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
        border-radius: 6px; 
        padding: 20px 22px 10px 22px; 
        margin-bottom: 8px; 
    }
    
    /* --- BADGES --- */
    .badge { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; margin-right: 6px; }
    .badge-section { background-color: #cfe2ff; color: #084298; }
    .badge-status { background-color: #e2e3e5; color: #41464b; }
    
    /* --- TICKET CONTENT --- */
    .ticket-title { font-size: 1.25rem; font-weight: 700; color: #111; margin: 8px 0px 6px 0px; }
    .ticket-desc { color: #666; font-size: 0.9rem; line-height: 1.4; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .ticket-assignee { font-size: 0.8rem; color: #888; }
    .dot-indicator { height: 10px; width: 10px; background-color: #e06d53; border-radius: 50%; display: inline-block; margin-right: 10px; }
    
    /* Category Bar Styling */
    .cat-bar-container { display: flex; align-items: center; margin-bottom: 12px; }
    .cat-bar-label { width: 180px; font-size: 0.85rem; color: #555; }
    .cat-bar-track { flex-grow: 1; height: 10px; background-color: #e9ecef; margin: 0 15px; border-radius: 4px; overflow: hidden; }
    .cat-bar-fill { height: 100%; border-radius: 4px; }
    .cat-bar-count { font-weight: 700; font-size: 0.9rem; width: 30px; text-align: right; }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)


# --- AUTHENTICATION ---
def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["username"], st.secrets.get("AUTH_USERNAME", "admin")) and \
           hmac.compare_digest(st.session_state["password"], st.secrets.get("AUTH_PASSWORD", "admin")):
            st.session_state["password_correct"] = True
            del st.session_state["password"]; del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<p class='sub-header'>ASANA / DIVISION 5</p><h1 class='main-title'>Ticket desk</h1>", unsafe_allow_html=True)
    st.write("Please sign in to access the dashboard.")
    with st.form("login_form"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.form_submit_button("Sign in", on_click=password_entered)
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Invalid username or password")
    return False

if not check_password(): st.stop()


# --- DATABASE & ASANA API LOGIC ---
def get_db_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

@st.cache_data(ttl=600)
def fetch_asana_sections():
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}"}
    response = requests.get(f"https://app.asana.com/api/1.0/projects/{st.secrets['PROJECT_GID']}/sections", headers=headers)
    return {sec["name"]: sec["gid"] for sec in response.json().get("data", [])} if response.ok else {}

@st.cache_data(ttl=3600)
def fetch_asana_users():
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}"}
    proj_res = requests.get(f"https://app.asana.com/api/1.0/projects/{st.secrets['PROJECT_GID']}", headers=headers)
    if not proj_res.ok: return {}
    workspace_gid = proj_res.json().get("data", {}).get("workspace", {}).get("gid")
    
    users_res = requests.get(f"https://app.asana.com/api/1.0/users?workspace={workspace_gid}&opt_fields=name", headers=headers)
    return {u["name"]: u["gid"] for u in users_res.json().get("data", []) if u.get("name")} if users_res.ok else {}

def move_task_to_section_in_asana(task_gid, section_gid, section_name):
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}", "Content-Type": "application/json"}
    requests.post(f"https://app.asana.com/api/1.0/sections/{section_gid}/addTask", json={"data": {"task": task_gid}}, headers=headers).raise_for_status()
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE tasks SET section_gid = %s, section_name = %s, modified_at = NOW() WHERE gid = %s", (section_gid, section_name, task_gid))

def assign_task_in_asana(task_gid, user_gid, user_name):
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}", "Content-Type": "application/json"}
    requests.put(f"https://app.asana.com/api/1.0/tasks/{task_gid}", json={"data": {"assignee": user_gid}}, headers=headers).raise_for_status()
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE tasks SET assignee_gid = %s, assignee_name = %s, modified_at = NOW() WHERE gid = %s", (user_gid, user_name if user_gid else None, task_gid))

def toggle_task_status_in_asana(gid, current_status):
    new_status = not current_status
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}", "Content-Type": "application/json"}
    requests.put(f"https://app.asana.com/api/1.0/tasks/{gid}", json={"data": {"completed": new_status}}, headers=headers).raise_for_status()
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE tasks SET completed = %s, modified_at = NOW() WHERE gid = %s", (new_status, gid))

def add_comment_to_asana(gid, text):
    headers = {"Authorization": f"Bearer {st.secrets['ASANA_TOKEN']}", "Content-Type": "application/json"}
    requests.post(f"https://app.asana.com/api/1.0/tasks/{gid}/stories", json={"data": {"text": text}}, headers=headers).raise_for_status()

def query_dashboard(category, status, assignee, overdue, search, section, date_range=None):
    conn = get_db_connection()
    try:
        conditions = []; values = []
        if category and category != "All": conditions.append("category = %s"); values.append(category)
        if section and section != "All": conditions.append("section_name = %s"); values.append(section)
        
        if status == "Open": conditions.append("completed = FALSE AND active = TRUE")
        elif status == "Completed": conditions.append("completed = TRUE")
        elif status == "Removed": conditions.append("active = FALSE")
        elif status == "Active": conditions.append("active = TRUE")

        if assignee and assignee != "Everyone":
            if assignee == "Unassigned": conditions.append("assignee_name IS NULL")
            else: conditions.append("assignee_name = %s"); values.append(assignee)

        if overdue: conditions.append("completed = FALSE AND active = TRUE AND due_on < CURRENT_DATE")
        if search:
            conditions.append("(name ILIKE %s OR description ILIKE %s OR assignee_name ILIKE %s)")
            values.extend([f"%{search}%"] * 3)

        if date_range:
            if len(date_range) == 2:
                conditions.append("due_on >= %s AND due_on <= %s")
                values.extend([date_range[0], date_range[1]])
            elif len(date_range) == 1:
                conditions.append("due_on = %s")
                values.append(date_range[0])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM tasks {where_clause} ORDER BY completed ASC, due_on NULLS LAST, modified_at DESC NULLS LAST, name"
        df = pd.read_sql(query, conn, params=values)

        with conn.cursor() as cur:
            cur.execute("SELECT category, COUNT(*) FROM tasks WHERE active = TRUE GROUP BY category ORDER BY COUNT(*) DESC, category")
            categories = cur.fetchall()
            cur.execute("SELECT section_name, COUNT(*) FROM tasks WHERE active = TRUE AND section_name IS NOT NULL GROUP BY section_name")
            sections = cur.fetchall()
            cur.execute("SELECT DISTINCT assignee_name FROM tasks WHERE active = TRUE AND assignee_name IS NOT NULL ORDER BY assignee_name")
            assignees = ["Everyone", "Unassigned"] + [row[0] for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FILTER (WHERE active), COUNT(*) FILTER (WHERE active AND NOT completed), COUNT(*) FILTER (WHERE active AND completed), COUNT(*) FILTER (WHERE active AND NOT completed AND due_on < CURRENT_DATE), COUNT(*) FILTER (WHERE NOT active) FROM tasks")
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
        if sections_map.get(new_sec):
            move_task_to_section_in_asana(task_gid, sections_map.get(new_sec), new_sec)
            st.toast(f"Moved to {new_sec}")

def handle_reassign(task_gid, widget_key, current_assignee):
    new_assignee = st.session_state[widget_key]
    if new_assignee != current_assignee:
        users_map = fetch_asana_users()
        user_gid = users_map.get(new_assignee) if new_assignee != "Unassigned" else None
        assign_task_in_asana(task_gid, user_gid, new_assignee)
        st.toast(f"Assigned to {new_assignee}")


# --- SIDEBAR / FILTERS ---
st.sidebar.markdown("<p style='color:#e06d53; font-weight:700; font-size:0.75rem; letter-spacing:1px;'>ORGANIZE</p>", unsafe_allow_html=True)
search_query = st.sidebar.text_input("Find a ticket", placeholder="Name, detail, person...", label_visibility="visible")
date_range = st.sidebar.date_input("Due Date Range", value=[], help="Select start and end dates.")
status_filter = st.sidebar.selectbox("Status", ["All tickets", "Open", "Completed", "Active", "Removed"], index=1)

_df, cat_list, sec_list, assign_options, stats, sync_run = query_dashboard("", "All tickets", "Everyone", False, "", "All", None)

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
    st.markdown("<p class='sub-header'>ASANA / DIVISION 5</p><h1 class='main-title'>Ticket desk</h1><p class='main-tagline'>A focused view of what needs attention, grouped by what each ticket is for.</p>", unsafe_allow_html=True)
with col_logout:
    st.markdown(f"<p style='text-align:right; font-size:0.85rem; color:#777;'>{stats[0]} active tickets</p>", unsafe_allow_html=True)
    if st.button("Sign out"):
        st.session_state["password_correct"] = False; st.rerun()

st.markdown(f"""
<div class="metric-container">
    <div class="metric-box"><span class="metric-label">Total</span><span class="metric-value">{stats[0]}</span></div>
    <div class="metric-box"><span class="metric-label">Open</span><span class="metric-value">{stats[1]}</span></div>
    <div class="metric-box"><span class="metric-label">Completed</span><span class="metric-value">{stats[2]}</span></div>
    <div class="metric-box"><span class="metric-label">Overdue</span><span class="metric-value">{stats[3]}</span></div>
    <div class="metric-box"><span class="metric-label">Archived</span><span class="metric-value">{stats[4]}</span></div>
</div>
""", unsafe_allow_html=True)

df, _, _, _, _, sync_run = query_dashboard(category_filter, status_filter, assignee_filter, overdue_filter, search_query, section_filter, date_range)


# --- SETUP TABS ---
tab_queue, tab_analytics = st.tabs(["🗂️ Work Queue", "📈 Analytics & Insights"])

# --- TAB 1: WORK QUEUE ---
with tab_queue:
    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        st.markdown(f"<h2 style='font-size:1.6rem; font-weight:800; margin-top:0px; margin-bottom:0px;'>{len(df)} matching tickets</h2>", unsafe_allow_html=True)
        last_sync_str = sync_run[1].strftime("%b %d, %Y at %I:%M %p") if sync_run[1] else "Never"
        st.markdown(f"<p style='font-size:0.8rem; color:#888; margin-bottom:15px;'>Last sync: {last_sync_str} · {sync_run[0].title()}</p>", unsafe_allow_html=True)
    with col_q2:
        if st.button("🔄 Sync now", type="secondary", use_container_width=True):
            with st.spinner("Syncing..."):
                run_sync(); st.cache_data.clear(); st.rerun()

    # --- CATEGORY BAR CHART ---
    if not df.empty:
        cat_counts = df['category'].value_counts()
        max_val = cat_counts.max()
        
        st.markdown("<div style='margin-bottom: 25px;'>", unsafe_allow_html=True)
        for cat, count in cat_counts.items():
            width_pct = int((count / max_val) * 100) if max_val > 0 else 0
            cat_colors = get_category_colors(cat)
            st.markdown(f"""
            <div class="cat-bar-container">
                <div class="cat-bar-label">{cat}</div>
                <div class="cat-bar-track">
                    <div class="cat-bar-fill" style="width: {width_pct}%; background-color: {cat_colors['bar']};"></div>
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
        
        st.download_button(label="Export CSV ↓", data=output.getvalue(), file_name="ticket-export.csv", mime="text/csv")
        st.divider()

    # Pagination Logic
    ITEMS_PER_PAGE = 20
    total_pages = math.ceil(len(df) / ITEMS_PER_PAGE) if not df.empty else 1
    if "page" not in st.session_state: st.session_state.page = 1
    if st.session_state.page > total_pages: st.session_state.page = total_pages

    start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    paged_df = df.iloc[start_idx:end_idx]

    @st.dialog("Ticket Details")
    def show_ticket_modal(gid):
        task, history = fetch_ticket_details(gid)
        if not task: return st.error("Ticket not found.")
        
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
        st.write(task.get("description") or "*No description provided.*")
        if task.get("asana_url"): st.markdown(f"[View in Asana]({task.get('asana_url')})")
        
        st.markdown("---")
        st.markdown("**Add a Comment:**")
        new_comment = st.text_area("Message", label_visibility="collapsed", placeholder="Type a comment to send to Asana...")
        if st.button("Post Comment"):
            with st.spinner("Posting..."):
                try:
                    add_comment_to_asana(gid, new_comment)
                    st.success("Comment posted successfully!")
                except Exception as e:
                    st.error(f"Failed to post comment: {e}")

        st.markdown("---")
        is_completed = task.get("completed", False)
        if st.button("✅ Mark as Completed" if not is_completed else "↩️ Reopen Ticket", type="primary"):
            with st.spinner("Updating Asana..."):
                toggle_task_status_in_asana(gid, is_completed); st.rerun() 
                    
        with st.expander("View History Log"):
            if history:
                for changed_at, change_type, details in history:
                    st.caption(f"• **{change_type.title()}** on {changed_at.strftime('%Y-%m-%d %H:%M')} — {details}")
            else:
                st.caption("No history recorded.")

    def render_tickets(dataframe):
        try:
            sections_map = fetch_asana_sections()
            section_names = list(sections_map.keys())
            users_map = fetch_asana_users()
            user_names = ["Unassigned"] + list(users_map.keys())
        except Exception:
            section_names, user_names = [], ["Unassigned"]

        for _, row in dataframe.iterrows():
            status_text = "Completed" if row["completed"] else "Open"
            current_sec = row.get("section_name") or "No Dept"
            current_assignee = row.get("assignee_name") or "Unassigned"
            cat_colors = get_category_colors(row['category'])
            
            with st.container():
                st.markdown(f"""
                <div class="ticket-card">
                    <div><span class="dot-indicator"></span><span class="badge badge-section">{current_sec}</span><span class="badge" style="background-color: {cat_colors['bg']}; color: {cat_colors['text']};">{row['category']}</span><span class="badge badge-status">{status_text}</span></div>
                    <div class="ticket-title">{row['name']}</div>
                    <div class="ticket-desc">{row['description']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Columns for actions
                col_btn1, col_btn2, col_sec, col_assign, col_blank = st.columns([1.5, 1.5, 2.5, 2.5, 1])
                
                with col_btn1:
                    if st.button("🔍 Details", key=f"btn_{row['gid']}", type="tertiary"): show_ticket_modal(row['gid'])
                with col_btn2:
                    if st.button("↩️ Reopen" if row["completed"] else "✅ Finish", key=f"q_{row['gid']}", type="tertiary"):
                        toggle_task_status_in_asana(row['gid'], row["completed"]); st.rerun()
                with col_sec:
                    if section_names:
                        idx = section_names.index(current_sec) if current_sec in section_names else 0
                        st.selectbox("Move:", section_names, index=idx, key=f"s_{row['gid']}", on_change=handle_quick_move, args=(row['gid'], f"s_{row['gid']}", current_sec), label_visibility="collapsed")
                with col_assign:
                    if user_names:
                        idx = user_names.index(current_assignee) if current_assignee in user_names else 0
                        st.selectbox("Assign:", user_names, index=idx, key=f"a_{row['gid']}", on_change=handle_reassign, args=(row['gid'], f"a_{row['gid']}", current_assignee), label_visibility="collapsed")
                
                st.markdown("<div style='margin-bottom: 28px;'></div>", unsafe_allow_html=True)

    if paged_df.empty:
        st.info("No tickets found matching your filters.")
    else:
        render_tickets(paged_df)
        
        # Pagination Controls
        st.markdown("---")
        col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
        with col_p1:
            if st.button("⬅️ Previous") and st.session_state.page > 1:
                st.session_state.page -= 1
                st.rerun()
        with col_p2:
            st.markdown(f"<p style='text-align:center; color:#666;'>Page {st.session_state.page} of {total_pages}</p>", unsafe_allow_html=True)
        with col_p3:
            if st.button("Next ➡️") and st.session_state.page < total_pages:
                st.session_state.page += 1
                st.rerun()

# --- TAB 2: ANALYTICS & INSIGHTS ---
with tab_analytics:
    st.markdown("<h3 style='color: #1a1a1a;'>Dashboard Intelligence</h3>", unsafe_allow_html=True)
    st.markdown("Data based on your current filter selection.", unsafe_allow_html=True)
    st.divider()

    if df.empty:
        st.info("Not enough data to generate analytics.")
    else:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['modified_at'] = pd.to_datetime(df['modified_at'], errors='coerce')
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.markdown("**🚨 Bottleneck Tracking** (Open Tickets by Dept)")
            open_df = df[~df['completed']]
            if not open_df.empty:
                bottleneck = open_df['section_name'].fillna("No Dept").value_counts()
                st.bar_chart(bottleneck, color="#e06d53")
            else:
                st.success("No open tickets!")

        with col_a2:
            st.markdown("**⏱️ Velocity** (Avg Days to Close)")
            closed_df = df[df['completed']].copy()
            if not closed_df.empty:
                closed_df['days_to_close'] = (closed_df['modified_at'] - closed_df['created_at']).dt.days
                avg_days = closed_df['days_to_close'].mean()
                
                st.metric("Workspace Average", f"{avg_days:.1f} Days")
                st.markdown("<span style='font-size:0.8rem; color:#666;'>Avg days to close by Category</span>", unsafe_allow_html=True)
                cat_days = closed_df.groupby('category')['days_to_close'].mean()
                st.bar_chart(cat_days, color="#6b8e72")
            else:
                st.info("No completed tickets to measure yet.")

        st.divider()
        st.markdown("**📅 Incoming Volume** (Tickets created per week)")
        vol_df = df.copy()
        vol_df = vol_df.dropna(subset=['created_at'])
        if not vol_df.empty:
            vol_df['Week'] = vol_df['created_at'].dt.to_period('W').dt.start_time
            weekly_counts = vol_df.groupby('Week').size()
            st.line_chart(weekly_counts, color="#5b7b9a")
