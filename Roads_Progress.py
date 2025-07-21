import os
import socket
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from branca.element import Template, MacroElement
import gspread
from datetime import datetime

# --- Constants ---
ON_CLOUD = "streamlitapp.com" in socket.gethostname()

# --- Google Sheets Setup ---
def get_worksheet():
    creds = {
        "type": st.secrets["gspread"]["type"],
        "project_id": st.secrets["gspread"]["project_id"],
        "private_key_id": st.secrets["gspread"]["private_key_id"],
        "private_key": st.secrets["gspread"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["gspread"]["client_email"],
        "client_id": st.secrets["gspread"]["client_id"],
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    gc = gspread.service_account_from_dict(creds)
    sheet = gc.open_by_url(st.secrets["gspread"]["sheet_url"])
    try:
        return sheet.worksheet("progress")
    except:
        return sheet.add_worksheet(title="progress", rows="1000", cols="3")

# --- Load shapefile ---
@st.cache_data
def load_shapefile():
    shp_path = "data/Rural_Suburbs_Allocation.shp"
    if not os.path.exists(shp_path):
        raise FileNotFoundError(f"Shapefile not found at {shp_path}")
    gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
    return gdf

# --- Load completed from Google Sheets ---
def load_completed():
    worksheet = get_worksheet()
    records = worksheet.get_all_records()
    completed = {}
    for row in records:
        editor = row["editor"]
        suburb = row["suburb"]
        completed.setdefault(editor, set()).add(suburb)
    return completed

# --- Save completed suburbs to Google Sheets ---
def save_completed(editor, selected_suburbs):
    worksheet = get_worksheet()
    all_rows = worksheet.get_all_records()
    existing = {(row['editor'], row['suburb']) for row in all_rows}

    new_rows = []
    for suburb in selected_suburbs:
        key = (editor, suburb)
        if key not in existing:
            new_rows.append([editor, suburb, datetime.now().isoformat()])

    if new_rows:
        worksheet.append_rows(new_rows)

# --- Assign colors ---
def get_editor_colors(editors):
    palette = ["red", "blue", "green", "orange", "purple", "pink", "cyan", "lime", "brown", "magenta"]
    return {editor: palette[i % len(palette)] for i, editor in enumerate(editors)}

# --- App layout ---
st.set_page_config(layout="wide")
st.title("🛣️ Rural Road Editing Progress Tracker")

# --- Load data ---
gdf = load_shapefile()
completed_suburbs_by_editor = load_completed()

# --- Validate fields ---
required_cols = {"NAME", "Assigned"}
if not required_cols.issubset(gdf.columns):
    st.error(f"Missing required columns: {required_cols - set(gdf.columns)}")
    st.stop()

editors = sorted(gdf["Assigned"].dropna().unique())
selected_editor = st.sidebar.selectbox("👤 Select your name (editor)", editors)

editor_suburbs_df = gdf[gdf["Assigned"] == selected_editor].sort_values("NAME")
editor_suburb_names = editor_suburbs_df["NAME"].tolist()
previously_selected = list(completed_suburbs_by_editor.get(selected_editor, set()))

# --- Sidebar selection ---
selected_suburbs = st.sidebar.multiselect(
    f"✅ Mark suburbs completed by {selected_editor}",
    options=editor_suburb_names,
    default=previously_selected
)

if selected_suburbs:
    st.sidebar.markdown("### ✅ Completed suburbs:")
    for suburb in sorted(selected_suburbs):
        st.sidebar.write(f"• {suburb}")
else:
    st.sidebar.info("No suburbs marked as completed yet.")

# Save changes
save_completed(selected_editor, selected_suburbs)
completed_suburbs_by_editor = load_completed()

# --- Mark status per suburb ---
def determine_status(row):
    for editor, suburbs in completed_suburbs_by_editor.items():
        if row["NAME"] in suburbs:
            return "Complete", editor
    return "Not Started", None

status_editor_list = gdf.apply(lambda row: determine_status(row), axis=1)
gdf["status"] = status_editor_list.str[0]
gdf["EditorDone"] = status_editor_list.str[1]

editor_colors = get_editor_colors(editors)

# --- Map ---
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
        tooltip=f"{row['NAME']} ({row['Assigned']}) - {row['status']}"
    ).add_to(m)

# Legend
legend_html = "".join(
    f"<i style='background:{color};width:12px;height:12px;display:inline-block;'></i> {editor}<br>"
    for editor, color in editor_colors.items()
)
legend_html += "<i style='background:gray;width:12px;height:12px;display:inline-block;'></i> Not Started"

legend_template = f"""
{{% macro html(this, kwargs) %}}
<div style="position: fixed; bottom: 40px; left: 40px; z-index: 9999;
background-color: white; padding: 10px; border: 2px solid grey;
box-shadow: 2px 2px 6px rgba(0,0,0,0.3); font-size: 14px;">
    <b>Legend</b><br>{legend_html}
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

# --- Editor Summary ---
st.subheader("👥 Editor Progress Summary")
summary = []
for editor in editors:
    assigned_df = gdf[gdf["Assigned"] == editor]
    completed = len(assigned_df[assigned_df["NAME"].isin(completed_suburbs_by_editor.get(editor, set()))])
    total = len(assigned_df)
    summary.append({
        "Editor": editor,
        "Completed": completed,
        "Total": total,
        "Progress (%)": round((completed / total) * 100, 1) if total else 0
    })

st.dataframe(pd.DataFrame(summary), use_container_width=True)
