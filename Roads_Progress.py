import os
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
import csv
from github import Github
from branca.element import Template, MacroElement

# --- Config & Secrets ---
# Ensure these are set in Streamlit Cloud -> Settings -> Secrets
SAVE_FILE = "completed_suburbs.csv"
ASSIGNMENT_FILE = "assignments.csv"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
REPO_NAME = st.secrets.get("REPO_NAME")

# --- GitHub Persistence Logic ---
def push_to_github(file_path, commit_message):
    """Saves the local CSV changes back to your GitHub repository."""
    if not GITHUB_TOKEN or not REPO_NAME:
        st.warning("GitHub Secrets not set. Changes saved to local session only.")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Read the local file content
        with open(file_path, "r") as f:
            content = f.read()
            
        try:
            # If file exists, update it
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_message, content, contents.sha)
        except Exception:
            # If file doesn't exist, create it
            repo.create_file(file_path, commit_message, content)
    except Exception as e:
        st.error(f"Error syncing with GitHub: {e}")

# --- Data Loading Functions ---
@st.cache_data
def load_shapefile():
    shp_path = "data/Rural_Suburbs_Allocation.shp"
    if not os.path.exists(shp_path):
        st.error(f"Shapefile not found at {shp_path}. Please check your folder structure.")
        st.stop()
    
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(epsg=4326)
    
    # Apply manual assignment overrides from CSV if it exists
    if os.path.exists(ASSIGNMENT_FILE):
        overrides = pd.read_csv(ASSIGNMENT_FILE)
        mapping = dict(zip(overrides['SUBURB'], overrides['Assigned']))
        gdf['Assigned'] = gdf['SUBURB'].map(mapping).fillna(gdf['Assigned'])
        
    return gdf

def load_completed():
    completed = {}
    if os.path.exists(SAVE_FILE):
        df = pd.read_csv(SAVE_FILE)
        for _, row in df.iterrows():
            editor = str(row["Editor"]).strip()
            suburb = str(row["Suburb"]).strip()
            if editor and suburb:
                completed.setdefault(editor, set()).add(suburb)
    return completed

def save_completed(editor, suburbs_selected):
    completed = load_completed()
    completed[editor] = set(suburbs_selected)
    with open(SAVE_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Editor", "Suburb"])
        for ed, subs in completed.items():
            for suburb in subs:
                writer.writerow([ed, suburb])
    
    # Trigger GitHub Sync
    push_to_github(SAVE_FILE, f"Update completed suburbs for {editor}")

def get_editor_colors(editor_list):
    palette = ["red", "blue", "green", "orange", "purple", "pink", "cyan", "lime", "brown", "magenta"]
    return {editor: palette[i % len(palette)] for i, editor in enumerate(editor_list)}

# --- UI Setup ---
st.set_page_config(layout="wide", page_title="Road Editing Tracker")
st.title("🛣️ Rural Road Editing Progress Tracker")

# Initial Data Load
gdf = load_shapefile()
completed_suburbs_by_editor = load_completed()
editors = sorted(gdf["Assigned"].dropna().unique())

# --- Sidebar: Admin Reassignment ---
with st.sidebar.expander("⚙️ Admin: Reassign Suburbs"):
    st.write("Change which editor is assigned to a suburb.")
    all_suburbs_list = sorted(gdf["SUBURB"].unique())
    sub_to_change = st.selectbox("Select Suburb to Reassign", all_suburbs_list)
    
    current_owner = gdf[gdf["SUBURB"] == sub_to_change]["Assigned"].values[0]
    st.info(f"Currently assigned to: **{current_owner}**")
    
    new_owner = st.selectbox("Assign to new Editor:", editors)
    
    if st.button("Confirm Reassignment"):
        if os.path.exists(ASSIGNMENT_FILE):
            ov_df = pd.read_csv(ASSIGNMENT_FILE)
        else:
            ov_df = pd.DataFrame(columns=["SUBURB", "Assigned"])
        
        # Update or add new record
        if sub_to_change in ov_df["SUBURB"].values:
            ov_df.loc[ov_df["SUBURB"] == sub_to_change, "Assigned"] = new_owner
        else:
            new_row = pd.DataFrame([{"SUBURB": sub_to_change, "Assigned": new_owner}])
            ov_df = pd.concat([ov_df, new_row], ignore_index=True)
        
        ov_df.to_csv(ASSIGNMENT_FILE, index=False)
        push_to_github(ASSIGNMENT_FILE, f"Reassigned {sub_to_change} to {new_owner}")
        
        st.success(f"Successfully moved {sub_to_change} to {new_owner}!")
        st.cache_data.clear() # Clear cache so shapefile reloads with new names
        st.rerun()

# --- Sidebar: User Progress ---
st.sidebar.markdown("---")
selected_editor = st.sidebar.selectbox("👤 Select your name (editor)", editors)

editor_suburbs_df = gdf[gdf["Assigned"] == selected_editor].sort_values("SUBURB")
editor_suburb_names = editor_suburbs_df["SUBURB"].tolist()
previously_selected = list(completed_suburbs_by_editor.get(selected_editor, set()))

selected_suburbs = st.sidebar.multiselect(
    f"✅ Mark suburbs completed by {selected_editor}",
    options=editor_suburb_names,
    default=[s for s in previously_selected if s in editor_suburb_names]
)

if st.sidebar.button("💾 Save Progress"):
    save_completed(selected_editor, selected_suburbs)
    st.sidebar.success("Progress Saved & Synced to GitHub!")
    st.rerun()

# --- Map Processing ---
def determine_status(row):
    for editor, suburbs in completed_suburbs_by_editor.items():
        if row["SUBURB"] in suburbs:
            return "Complete", editor
    return "Not Started", None

status_data = gdf.apply(determine_status, axis=1)
gdf["status"] = [s[0] for s in status_data]
gdf["EditorDone"] = [s[1] for s in status_data]

editor_colors = get_editor_colors(editors)

# --- Map Rendering ---
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=10)

for _, row in gdf.iterrows():
    color = editor_colors.get(row["EditorDone"], "gray") if row["status"] == "Complete" else "gray"
    folium.GeoJson(
        row["geometry"],
        style_function=lambda _, color=color: {
            "fillColor": color, "color": "black", "weight": 0.5, "fillOpacity": 0.5
        },
        tooltip=f"<b>{row['SUBURB']}</b><br>Assigned: {row['Assigned']}<br>Status: {row['status']}"
    ).add_to(m)

# --- Fixed Legend Logic (Avoids SyntaxError) ---
legend_items_html = "".join([
    f"<i style='background:{c};width:12px;height:12px;display:inline-block;'></i> {e}<br>" 
    for e, c in editor_colors.items()
])

legend_template = """
{% macro html(this, kwargs) %}
<div style="
    position: fixed; 
    bottom: 50px; 
    left: 50px; 
    width: 160px; 
    background-color: white; 
    border: 2px solid grey; 
    z-index: 9999; 
    padding: 10px;
    font-size: 14px;
">
    <b>Legend</b><br>
    {{ITEMS}}
    <i style='background:gray;width:12px;height:12px;display:inline-block;'></i> Not Started
</div>
{% endmacro %}
""".replace("{{ITEMS}}", legend_items_html)

legend = MacroElement()
legend._template = Template(legend_template)
m.get_root().add_child(legend)

st_folium(m, width=1000, height=600)

# --- Progress Stats ---
st.markdown("---")
st.subheader("📊 Statistics & Summary")
col1, col2 = st.columns([1, 2])

total_count = len(gdf)
completed_count = len(gdf[gdf["status"] == "Complete"])
percent = round((completed_count / total_count) * 100, 1)

with col1:
    st.metric("Total Completion", f"{percent}%", f"{completed_count} / {total_count} Suburbs")

with col2:
    st.progress(completed_count / total_count)
    
summary_data = []
for ed in editors:
    ed_total = len(gdf[gdf["Assigned"] == ed])
    ed_done = len(gdf[(gdf["Assigned"] == ed) & (gdf["status"] == "Complete")])
    summary_data.append({
        "Editor": ed, 
        "Completed": ed_done, 
        "Total": ed_total, 
        "Progress": f"{round((ed_done/ed_total)*100 if ed_total > 0 else 0, 1)}%"
    })

st.table(pd.DataFrame(summary_data))

