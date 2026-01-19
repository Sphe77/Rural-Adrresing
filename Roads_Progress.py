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
SAVE_FILE = "completed_suburbs.csv"
ASSIGNMENT_FILE = "assignments.csv"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
REPO_NAME = st.secrets.get("REPO_NAME")

# --- GitHub Persistence ---
def push_to_github(file_path, commit_message):
    if not GITHUB_TOKEN or not REPO_NAME:
        st.warning("GitHub Secrets not set. Saving locally only.")
        return
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        with open(file_path, "r") as f:
            content = f.read()
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_message, content, contents.sha)
        except:
            repo.create_file(file_path, commit_message, content)
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")

# --- Data Loading ---
@st.cache_data
def load_shapefile():
    shp_path = "data/Rural_Suburbs_Allocation.shp"
    if not os.path.exists(shp_path):
        st.error(f"Shapefile not found at {shp_path}")
        st.stop()
    
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(epsg=4326)
    
    # Apply manual assignment overrides
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
    push_to_github(SAVE_FILE, f"Update completed suburbs for {editor}")

def get_editor_colors(editor_list):
    palette = ["red", "blue", "green", "orange", "purple", "pink", "cyan", "lime", "brown", "magenta"]
    return {editor: palette[i % len(palette)] for i, editor in enumerate(editor_list)}

# --- UI Setup ---
st.set_page_config(layout="wide", page_title="Road Editing Tracker")
st.title("🛣️ Rural Road Editing Progress Tracker")

gdf = load_shapefile()
completed_suburbs_by_editor = load_completed()
editors = sorted(gdf["Assigned"].dropna().unique())

# --- Sidebar: Admin Reassignment ---
with st.sidebar.expander("⚙️ Admin: Reassign Suburbs"):
    all_suburbs_list = sorted(gdf["SUBURB"].unique())
    sub_to_change = st.selectbox("Select Suburb", all_suburbs_list)
    current_owner = gdf[gdf["SUBURB"] == sub_to_change]["Assigned"].values[0]
    st.info(f"Currently: **{current_owner}**")
    new_owner = st.selectbox("Assign to:", editors)
    
    if st.button("Confirm Reassignment"):
        ov_df = pd.read_csv(ASSIGNMENT_FILE) if os.path.exists(ASSIGNMENT_FILE) else pd.DataFrame(columns=["SUBURB", "Assigned"])
        if sub_to_change in ov_df["SUBURB"].values:
            ov_df.loc[ov_df["SUBURB"] == sub_to_change, "Assigned"] = new_owner
        else:
            ov_df = pd.concat([ov_df, pd.DataFrame([{"SUBURB": sub_to_change, "Assigned": new_owner}])], ignore_index=True)
        ov_df.to_csv(ASSIGNMENT_FILE, index=False)
        push_to_github(ASSIGNMENT_FILE, f"Reassigned {sub_to_change} to {new_owner}")
        st.success("Reassigned!")
        st.cache_data.clear()
        st.rerun()

# --- Sidebar: Editor Progress ---
<<<<<<< HEAD
=======
st.sidebar.markdown("---")
>>>>>>> fc0e1a57c01614849fe5874e575cde59e43284ec
selected_editor = st.sidebar.selectbox("👤 Select your name", editors)
editor_suburbs = gdf[gdf["Assigned"] == selected_editor]["SUBURB"].tolist()
previously_selected = list(completed_suburbs_by_editor.get(selected_editor, set()))

selected_suburbs = st.sidebar.multiselect(
    f"✅ Completed by {selected_editor}",
    options=editor_suburbs,
    default=[s for s in previously_selected if s in editor_suburbs]
)

if st.sidebar.button("💾 Save Progress"):
    save_completed(selected_editor, selected_suburbs)
    st.sidebar.success("Saved & Synced!")
    st.rerun()

# --- Process Status ---
def determine_status(row):
    for editor, suburbs in completed_suburbs_by_editor.items():
<<<<<<< HEAD
        if row["SUBURB"] in suburbs: return "Complete", editor
=======
        if row["SUBURB"] in suburbs: 
            return "Complete", editor
>>>>>>> fc0e1a57c01614849fe5874e575cde59e43284ec
    return "Not Started", None

status_data = gdf.apply(determine_status, axis=1)
gdf["status"] = [s[0] for s in status_data]
gdf["EditorDone"] = [s[1] for s in status_data]
editor_colors = get_editor_colors(editors)

# --- Map ---
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=10)
for _, row in gdf.iterrows():
    color = editor_colors.get(row["EditorDone"], "gray") if row["status"] == "Complete" else "gray"
    folium.GeoJson(
        row["geometry"],
        style_function=lambda _, color=color: {"fillColor": color, "color": "black", "weight": 0.5, "fillOpacity": 0.5},
<<<<<<< HEAD
        tooltip=f"{row['SUBURB']} | {row['Assigned']} | {row['status']}"
    ).add_to(m)

# --- Legend (Fixed) ---
legend_items_html = "".join([f"<i style='background:{c};width:12px;height:12px;display:inline-block;'></i> {e}<br>" for e, c in editor_colors.items()])
legend_template = """
{% macro html(this, kwargs) %}
<div style="position: fixed; bottom: 50px; left: 50px; width: 160px; background: white; border: 2px solid grey; z-index: 9999; padding: 10px;">
=======
        tooltip=f"{row['SUBURB']} | Assigned: {row['Assigned']} | Status: {row['status']}"
    ).add_to(m)

# --- Legend ---
legend_items_html = "".join([f"<i style='background:{c};width:12px;height:12px;display:inline-block;'></i> {e}<br>" for e, c in editor_colors.items()])
legend_template = """
{% macro html(this, kwargs) %}
<div style="position: fixed; bottom: 50px; left: 50px; width: 160px; background: white; border: 2px solid grey; z-index: 9999; padding: 10px; font-size: 14px;">
>>>>>>> fc0e1a57c01614849fe5874e575cde59e43284ec
<b>Legend</b><br>{{ITEMS}}<i style='background:gray;width:12px;height:12px;display:inline-block;'></i> Not Started</div>
{% endmacro %}
""".replace("{{ITEMS}}", legend_items_html)
legend = MacroElement(); legend._template = Template(legend_template)
m.get_root().add_child(legend)
st_folium(m, width=1000, height=500)

<<<<<<< HEAD
# --- AUDIT: Find that missing 0.5% ---
=======
# --- AUDIT: Find missing 0.5% ---
>>>>>>> fc0e1a57c01614849fe5874e575cde59e43284ec
st.markdown("---")
st.subheader("🔍 Missing Suburbs Audit")
incomplete = gdf[gdf["status"] != "Complete"]

if incomplete.empty:
<<<<<<< HEAD
    st.success("🎉 100% Complete!")
else:
    st.warning(f"Remaining {len(incomplete)} suburb(s) to reach 100%:")
    audit_df = incomplete[["SUBURB", "Assigned"]].fillna("⚠️ UNASSIGNED")
    st.dataframe(audit_df, use_container_width=True)

# --- Stats ---
st.subheader("📊 Stats")
total, done = len(gdf), len(gdf[gdf["status"] == "Complete"])
st.metric("Total Progress", f"{round((done/total)*100, 1)}%", f"{done}/{total}")
st.progress(done/total)
=======
    st.success("🎉 All suburbs are marked as complete! 100% reached.")
else:
    st.warning(f"Remaining {len(incomplete)} suburb(s) to reach 100%:")
    audit_df = incomplete[["SUBURB", "Assigned"]].fillna("⚠️ UNASSIGNED")
    st.dataframe(audit_df, use_container_width=True, hide_index=True)

# --- Editor Progress Summary ---
st.subheader("👥 Editor Progress Summary")
summary_data = []
for ed in editors:
    ed_gdf = gdf[gdf["Assigned"] == ed]
    total_assigned = len(ed_gdf)
    completed_count = len(ed_gdf[ed_gdf["status"] == "Complete"])
    
    if total_assigned > 0:
        prog = f"{round((completed_count / total_assigned) * 100, 1)}%"
    else:
        prog = "0%"
        
    summary_data.append({
        "Editor": ed, 
        "Completed": completed_count, 
        "Total Assigned": total_assigned, 
        "Progress": prog
    })

if summary_data:
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

# --- Total Progress Stats ---
st.subheader("📊 Overall Statistics")
total_all = len(gdf)
done_all = len(gdf[gdf["status"] == "Complete"])
st.metric("Total Completion", f"{round((done_all/total_all)*100, 1)}%", f"{done_all}/{total_all} Suburbs")
st.progress(done_all/total_all)


>>>>>>> fc0e1a57c01614849fe5874e575cde59e43284ec
