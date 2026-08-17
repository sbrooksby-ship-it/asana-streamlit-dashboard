import streamlit as st
import pandas as pd
import psycopg2
import hmac
import os
from asana_sync import main as run_sync

# --- SETUP & AUTHENTICATION ---
st.set_page_config(page_title="Asana Ticket Dashboard", layout="wide")

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if hmac.compare_digest(st.session_state["username"], st.secrets["AUTH_USERNAME"]) and \
           hmac.compare_digest(st.session_state["password"], st.secrets["AUTH_PASSWORD"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("Login to Asana Dashboard")
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.button("Login", on_click=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 User not known or password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if not authenticated

# --- LOGIC ---
@st.cache_resource
def get_db_connection():
    # Streamlit uses st.secrets for environment variables in the cloud
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def fetch_data(category, status, assignee, overdue, search):
    conn = get_db_connection()
    
    conditions = []
    values = []
    
    if category and category != "All":
        conditions.append("category = %s")
        values.append(category)
    
    if status == "Open":
        conditions.append("completed = FALSE AND active = TRUE")
    elif status == "Completed":
        conditions.append("completed = TRUE")
    elif status == "Removed":
        conditions.append("active = FALSE")
    elif status == "Active":
        conditions.append("active = TRUE")
        
    if assignee and assignee != "All":
        conditions.append("assignee_name = %s")
        values.append(assignee)
        
    if overdue:
        conditions.append("completed = FALSE AND active = TRUE AND due_on < CURRENT_DATE")
        
    if search:
        conditions.append("(name ILIKE %s OR description ILIKE %s OR assignee_name ILIKE %s)")
        values.extend([f"%{search}%"] * 3)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # Fetch Tasks
    query = f"""
        SELECT gid, name, category, completed, active, due_on, assignee_name, last_seen_at, asana_url
        FROM tasks {where_clause}
        ORDER BY completed ASC, due_on NULLS LAST, modified_at DESC NULLS LAST, name
    """
    df = pd.read_sql(query, conn, params=values)
    
    # Fetch Dropdown Options
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT category FROM tasks WHERE active = TRUE ORDER BY category")
        categories = ["All"] + [row[0] for row in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT assignee_name FROM tasks WHERE active = TRUE AND assignee_name IS NOT NULL ORDER BY assignee_name")
        assignees = ["All"] + [row[0] for row in cur.fetchall()]
        
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE active), 
                COUNT(*) FILTER (WHERE active AND completed),
                COUNT(*) FILTER (WHERE active AND NOT completed), 
                COUNT(*) FILTER (WHERE active AND NOT completed AND due_on < CURRENT_DATE),
                COUNT(*) FILTER (WHERE NOT active) 
            FROM tasks
        """)
        stats = cur.fetchone()
        
    return df, categories, assignees, stats

# --- UI DASHBOARD ---
st.title("📊 Asana Ticket Dashboard")

# Manual Sync Button
if st.button("🔄 Sync with Asana Now"):
    with st.spinner("Syncing tasks..."):
        try:
            # Temporarily set environment variables for the sync script to pick up
            os.environ["ASANA_TOKEN"] = st.secrets["ASANA_TOKEN"]
            os.environ["PROJECT_GID"] = st.secrets["PROJECT_GID"]
            os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
            run_sync()
            st.success("Sync completed successfully!")
            st.cache_data.clear() # Clear cache to show new data
        except Exception as e:
            st.error(f"Sync failed: {e}")

# Sidebar Filters
st.sidebar.header("Filters")
search_query = st.sidebar.text_input("Search (Name/Desc/Assignee)")
status_filter = st.sidebar.selectbox("Status", ["All", "Open", "Completed", "Active", "Removed"], index=1)
overdue_filter = st.sidebar.checkbox("Overdue Only", value=False)

# Need to fetch initial data to populate dynamic dropdowns safely
_df, cat_options, assign_options, stats = fetch_data(None, "All", None, False, "")

category_filter = st.sidebar.selectbox("Category", cat_options)
assignee_filter = st.sidebar.selectbox("Assignee", assign_options)

# Apply active filters
df, _, _, stats = fetch_data(category_filter, status_filter, assignee_filter, overdue_filter, search_query)

# Display Metrics
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Active", stats[0])
col2.metric("Completed", stats[1])
col3.metric("Open", stats[2])
col4.metric("Overdue", stats[3])
col5.metric("Removed", stats[4])

st.divider()

# Display Data
st.subheader(f"Tickets ({len(df)})")
if not df.empty:
    # Format the dataframe for display
    display_df = df.copy()
    # Create clickable Asana links
    display_df["asana_url"] = display_df["asana_url"].apply(lambda x: f'<a href="{x}" target="_blank">View</a>' if pd.notnull(x) else "")
    
    # Render table with HTML enabled for the links
    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # CSV Export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download data as CSV",
        data=csv,
        file_name='asana-tickets.csv',
        mime='text/csv',
    )
else:
    st.info("No tickets found matching your filters.")
