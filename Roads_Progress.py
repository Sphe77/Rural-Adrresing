import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from branca.element import Template, MacroElement  # For legend

# --- Load shapefile ---
@st.cache_data
def load_shapefile():
    shp_path = r"C:\Users\sphelele.ntilane\OneDrive - eThekwini Municipality\Desktop\Streamlit\Rural addressing\Rural_Suburbs_Allocation.shp"
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(epsg=4326)  # Reproject for folium compatibility
    return gdf

# --- Page setup ---
st.set_page_config(layout="wide")
st.title("🛣️ Rural Road Editing Progress Tracker")
st.markdown("Monitor editor progress by suburb (based on shapefile).")

# --- Load and validate data ---
gdf = load_shapefile()

required_cols = {"NAME", "Assigned"}
if not required_cols.issubset(gdf.columns):
    st.error(f"Shapefile is missing required columns: {required_cols - set(gdf.columns)}")
    st.stop()

# --- Initialize session state ---
if "editor_suburb_map" not in st.session_state:
    st.session_state.editor_suburb_map = {}

# --- Editor selection ---
editors = sorted(gdf["Assigned"].dropna().unique())
selected_editor = st.sidebar.selectbox("👤 Select your name (editor)", editors)

# --- Get suburbs for editor ---
editor_suburbs_df = gdf[gdf["Assigned"] == selected_editor].sort_values("NAME")
editor_suburb_names = editor_suburbs_df["NAME"].tolist()

# --- Track editor's selections ---
if selected_editor not in st.session_state.editor_suburb_map:
    st.session_state.editor_suburb_map[selected_editor] = set()

# --- Suburb selection multiselect ---
previously_selected = list(st.session_state.editor_suburb_map[selected_editor])
selected_suburbs = st.sidebar.multiselect(
    f"✅ Select suburbs completed by {selected_editor}",
    options=editor_suburb_names,
    default=previously_selected
)

# --- Display completed suburbs ---
if selected_suburbs:
    st.sidebar.markdown("### 🟢 Suburbs marked as completed:")
    for suburb in sorted(selected_suburbs):
        st.sidebar.write(f"• {suburb}")
else:
    st.sidebar.info("No suburbs marked as completed yet.")

# --- Update session state ---
st.session_state.editor_suburb_map[selected_editor] = set(selected_suburbs)

# --- Aggregate all completed suburbs ---
all_completed_suburbs = set()
for subs in st.session_state.editor_suburb_map.values():
    all_completed_suburbs.update(subs)

# --- Assign status to suburbs ---
gdf["status"] = gdf["NAME"].apply(
    lambda s: "Complete" if s in all_completed_suburbs else "Not Started"
)

# --- Map of suburb status ---
st.subheader("🗺️ Map of Suburb Completion Status")

def get_color(status):
    return {
        "Complete": "green",
        "Not Started": "gray"
    }.get(status, "gray")

# Create map
m = folium.Map(location=[-29.85, 30.98], zoom_start=10)

# Add suburbs to map
for _, row in gdf.iterrows():
    folium.GeoJson(
        row["geometry"],
        style_function=lambda _, status=row["status"]: {
            "fillColor": get_color(status),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.5
        },
        tooltip=f"{row['NAME']} ({row['Assigned']}) - {row['status']}"
    ).add_to(m)

# --- Add custom legend using MacroElement ---
legend_template = """
{% macro html(this, kwargs) %}
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    z-index: 9999;
    background-color: white;
    padding: 10px;
    border: 2px solid grey;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    font-size: 14px;
">
    <b>Legend</b><br>
    <i style="background:green; width:12px; height:12px; display:inline-block;"></i> Suburb Completed<br>
    <i style="background:gray; width:12px; height:12px; display:inline-block;"></i> Suburb Not Done
</div>
{% endmacro %}
"""
legend = MacroElement()
legend._template = Template(legend_template)
m.get_root().add_child(legend)

# --- Render map ---
st_folium(m, width=1000, height=600)

# --- Overall progress ---
st.subheader("📊 Overall Progress")
total_suburbs = len(gdf)
completed_total = len(gdf[gdf["status"] == "Complete"])
progress_percent = round((completed_total / total_suburbs) * 100, 1)

st.write(f"**{completed_total} / {total_suburbs} suburbs completed ({progress_percent}%)**")
st.progress(completed_total / total_suburbs)

# --- Editor progress summary ---
st.subheader("👥 Editor Progress Summary")
summary = []
for editor in editors:
    editor_df = gdf[gdf["Assigned"] == editor]
    completed = len(editor_df[editor_df["status"] == "Complete"])
    total = len(editor_df)
    summary.append({
        "Editor": editor,
        "Completed": completed,
        "Total": total,
        "Progress (%)": round((completed / total * 100), 1) if total > 0 else 0
    })

summary_df = pd.DataFrame(summary)
st.dataframe(summary_df, use_container_width=True)

