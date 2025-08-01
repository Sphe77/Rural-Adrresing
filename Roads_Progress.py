import os
import socket
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
import csv
from branca.element import Template, MacroElement

SAVE_FILE = "completed_suburbs.csv"
ON_CLOUD = "streamlitapp.com" in socket.gethostname()
INIT_DONE_FLAG = "init_from_csv_done"

# --- Load shapefile ---
@st.cache_data
def load_shapefile():
    shp_path = "data/Rural_Suburbs_Allocation.shp"
    if not os.path.exists(shp_path):
        raise FileNotFoundError(f"Shapefile not found at {shp_path}")
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(epsg=4326)
    return gdf

# --- Load completed suburbs from CSV and associate with editors ---
def load_completed():
    if ON_CLOUD:
        if not st.session_state.get(INIT_DONE_FLAG):
            completed = {}
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for row in reader:
                        editor = row["Editor"].strip()
                        suburb = row["Suburb"].strip().upper()
                        completed.setdefault(editor, set()).add(suburb)
                st.session_state["completed_suburbs"] = completed
                st.session_state[INIT_DONE_FLAG] = True
            else:
                st.session_state["completed_suburbs"] = {}
        return st.session_state.get("completed_suburbs", {})

    # Local (non-cloud) behavior
    completed = {}
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                editor = row["Editor"].strip()
                suburb = row["Suburb"].strip().upper()
                completed.setdefault(editor, set()).add(suburb)
    return completed

# --- Save completed suburbs ---
def save_completed(editor, suburbs_selected):
    if ON_CLOUD:
        st.session_state.setdefault("completed_suburbs", {})
        st.session_state["completed_suburbs"][editor] = set(suburbs_selected)
        return
    completed = load_completed()
    completed[editor] = set(suburb.upper() for suburb in suburbs_selected)
    with open(SAVE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["Editor", "Suburb"])
        for ed, subs in completed.items():
            for suburb in subs:
                writer.writerow([ed, suburb])

# --- Assign editor colors ---
def get_editor_colors(editor_list):
    palette = [
        "red", "blue", "green", "orange", "purple",
        "pink", "cyan", "lime", "brown", "magenta"
    ]
    return {editor: palette[i % len(palette)] for i, editor in enumerate(editor_list)}

# --- Page setup ---
st.set_page_config(layout="wide")
st.title("🛣️ Rural Road Editing Progress Tracker")
st.markdown("Monitor editor progress by suburb (based on shapefile).")

# --- Load data ---
gdf = load_shapefile()
completed_suburbs_by_editor = load_completed()

required_cols = {"SUBURB", "Assigned"}
if not required_cols.issubset(gdf.columns):
    st.error(f"Shapefile is missing required columns: {required_cols - set(gdf.columns)}")
    st.stop()

editors = sorted(gdf["Assigned"].dropna().unique())
if not editors:
    st.error("No editors assigned in the shapefile. Please check the 'Assigned' column.")
    st.stop()

selected_editor = st.sidebar.selectbox("👤 Select your name (editor)", editors)

editor_suburbs_df = gdf[gdf["Assigned"] == selected_editor].sort_values("SUBURB")
editor_suburb_names = [s.strip().upper() for s in editor_suburbs_df["SUBURB"].tolist()]
previously_selected = list(completed_suburbs_by_editor.get(selected_editor, set()))

# --- Suburb selection ---
selected_suburbs = st.sidebar.multiselect(
    f"✅ Select suburbs completed by {selected_editor}",
    options=editor_suburb_names,
    default=previously_selected
)

if selected_suburbs:
    st.sidebar.markdown("### 🟢 Suburbs marked as completed:")
    for suburb in sorted(selected_suburbs):
        st.sidebar.write(f"• {suburb}")
else:
    st.sidebar.info("No suburbs marked as completed yet.")

save_completed(selected_editor, selected_suburbs)
completed_suburbs_by_editor = load_completed()

# --- Determine completion status per suburb ---
def determine_status(row):
    for editor, suburbs in completed_suburbs_by_editor.items():
        if row["SUBURB"].strip().upper() in suburbs:
            return "Complete", editor
    return "Not Started", None

status_editor_list = gdf.apply(lambda row: determine_status(row), axis=1)
gdf[["status", "EditorDone"]] = pd.DataFrame(status_editor_list.tolist(), index=gdf.index)

# --- Assign color per editor ---
editor_colors = get_editor_colors(editors)

# --- Map rendering ---
st.subheader("🗺️ Map of Suburb Completion Status")

def get_color(row):
    if row["status"] == "Complete" and row["EditorDone"] in editor_colors:
        return editor_colors[row["EditorDone"]]
    return "gray"

m = folium.Map(location=[-29.85, 30.98], zoom_start=10)

for _, row in gdf.iterrows():
    color = get_color(row)
    folium.GeoJson(
        row["geometry"],
        style_function=lambda _, color=color: {
            "fillColor": color,
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.5
        },
        tooltip=f"{row['SUBURB']} ({row['Assigned']}) - {row['status']}"
    ).add_to(m)

# --- Dynamic legend ---
legend_items = ""
for editor, color in editor_colors.items():
    legend_items += f"""<i style='background:{color};width:12px;height:12px;display:inline-block;'></i> {editor}<br>"""
legend_items += "<i style='background:gray;width:12px;height:12px;display:inline-block;'></i> Not Started"

legend_template = f"""
{{% macro html(this, kwargs) %}}
<div style="
    position: fixed;
    bottom: 10px;
    left: 10px;
    z-index: 9999;
    background-color: white;
    padding: 10px;
    border: 2px solid grey;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    font-size: 14px;
    max-height: 300px;
    overflow-y: auto;
">
    <b>Legend</b><br>
    {legend_items}
</div>
{{% endmacro %}}
"""

legend = MacroElement()
legend._template = Template(legend_template)
m.get_root().add_child(legend)

st_folium(m, width=1000, height=600)

# --- Overall Progress ---
st.subheader("📊 Overall Progress")
total_suburbs = len(gdf)
completed_total = len(gdf[gdf["status"] == "Complete"])
progress_percent = round((completed_total / total_suburbs) * 100, 1)

st.write(f"**{completed_total} / {total_suburbs} suburbs completed ({progress_percent}%)**")
st.progress(completed_total / total_suburbs)

# --- Editor Progress Summary ---
st.subheader("👥 Editor Progress Summary")
summary = []
for editor in editors:
    editor_df = gdf[gdf["Assigned"] == editor]
    completed = len(editor_df[editor_df["SUBURB"].apply(lambda s: s.strip().upper()).isin(completed_suburbs_by_editor.get(editor, set()))])
    total = len(editor_df)
    summary.append({
        "Editor": editor,
        "Completed": completed,
        "Total": total,
        "Progress (%)": round((completed / total * 100), 1) if total > 0 else 0
    })

summary_df = pd.DataFrame(summary)
st.dataframe(summary_df, use_container_width=True)
