import base64
import datetime
import logging
import os
from io import BytesIO

import folium
import leafmap.foliumap as leafmap
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
import streamlit as st
import streamlit.components.v1 as components
import xarray as xr
from dotenv import load_dotenv
from folium.plugins import BoatMarker, LocateControl
from minio import Minio
from streamlit_echarts import st_echarts
from streamlit_folium import st_folium
from urllib3.exceptions import MaxRetryError

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

AQUA_CONNECTIVITY_FILE_WITH_LOCALITY_ID_S3 = os.getenv(
    "AQUA_CONNECTIVITY_FILE_WITH_LOCALITY_ID_S3"
)
AQUA_OPENDRIFT_OUTPUT_FILE_S3 = os.getenv("AQUA_OPENDRIFT_OUTPUT_FILE_S3")
AQUA_SITE_FILE = os.getenv("AQUA_SITE_FILE")
AQUA_SITE_DISTANCES_FILES = os.getenv("AQUA_SITE_DISTANCES_FILES")

BW_CLIENT_ID = os.getenv("BW_CLIENT_ID")
BW_CLIENT_SECRET = os.getenv("BW_CLIENT_SECRET")


def get_token():
    """Get time-limited token for API access using client id and password"""
    data = {
        "client_id": BW_CLIENT_ID,
        "scope": "api",
        "client_secret": BW_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }

    resp = requests.post("https://id.barentswatch.no/connect/token", data=data)
    token = resp.json()["access_token"]
    return token


def get_site_temperature(locality_id, year, token):
    headers = {"Authorization": f"Bearer {token}"}
    req = requests.get(
        f"https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/{locality_id}/seatemperature/{year}",
        headers=headers,
    )
    if req.ok:
        df_temp = pd.DataFrame(req.json()["data"])
    else:
        df_temp = pd.DataFrame()
    return df_temp


def get_site_licecount(locality_id, year, token):
    """Get average adult female lice count time series as DataFrame"""
    headers = {"Authorization": f"Bearer {token}"}
    req = requests.get(
        f"https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/{locality_id}/avgfemalelice/{year}",
        headers=headers,
    )
    if req.ok:
        lice_data = req.json()
        df_lice = pd.DataFrame(lice_data["data"]).rename(
            {"value": lice_data["type"]}, axis=1
        )

    else:
        df_lice = pd.DataFrame()
    return df_lice


def get_sites_info(week, year, token):
    """Get basic info on all sites for given year and week"""
    headers = {"Authorization": f"Bearer {token}"}

    req = requests.get(
        f"https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/{year}/{week}",
        headers=headers,
    )

    if req.ok:
        df_sites_info = (
            pd.DataFrame(req.json()["localities"])
            .sort_values("name")
            .set_index("localityNo")
        )
    else:
        df_sites_info = pd.DataFrame()

    return df_sites_info


def get_closest_sites(locality_id, N=10):
    """Get N closest sites to given locality"""
    # Load connectivity data and distance matrix
    df_dists = pd.read_excel(distances_file, index_col=0)
    df_locs = pd.read_excel(localities_file, index_col=0)

    # Sort by distance
    sorted_locality_ids = df_dists.loc[locality_id].sort_values().index[:10].values
    sorted_locality_names = [
        df_locs[df_locs["localityNo"] == idx]["name"].values[0]
        for idx in sorted_locality_ids
        if idx in df_locs["localityNo"].values
    ]
    # sorted_locality_names = [n for n in sorted_locality_names if n in df_connect.index.values]

    return sorted_locality_ids, sorted_locality_names


def plot_connectivity_echarts(locality_id):
    # Load connectivity data and distance matrix
    df_dists = pd.read_excel(distances_file, index_col=0)
    df_connect = pd.read_excel(connectivity_file, index_col=0)

    # Sort by distance
    sorted_locality_ids = df_dists.loc[locality_id].sort_values().index[:10]
    # sorted_locality_names = [df_locs[df_locs['localityNo'] == idx]['name'].values[0]
    #                         for idx in sorted_locality_ids
    #                         if idx in df_locs['localityNo'].values]

    # Re-order by distance to selected locality and plot
    df_connect = df_connect.loc[sorted_locality_ids, sorted_locality_ids]

    # Replace locality IDs by names in the truncated and sorted connectivity dataframe
    df_connect.index = df_locs.set_index("localityNo").loc[df_connect.index.values][
        "name"
    ]
    df_connect.columns = df_locs.set_index("localityNo").loc[df_connect.columns.values][
        "name"
    ]

    data = [
        [i, j, float(d) if d > 0 else "-"]
        for i, dd in enumerate(df_connect.values.T)
        for j, d in enumerate(dd)
    ]

    option = {
        "tooltip": {"position": "top"},
        "grid": {"height": "50%", "top": "10%", "left": "20%"},
        "xAxis": {
            "type": "category",
            "data": df_connect.columns.values.tolist(),
            "splitArea": {"show": True},
            "axisLabel": {"rotate": 90},
        },
        "yAxis": {
            "type": "category",
            "data": df_connect.index.values.tolist(),
            "splitArea": {"show": True},
        },
        "visualMap": {
            "min": 0,
            "max": 100,  # int(df_connect.max().max()),
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": "10%",
            "inRange": {
                "color": ["lightgreen", "darkred"],
            },
        },
        "series": [
            {
                "name": "Sites water contact potential",
                "type": "heatmap",
                "data": data,
                "label": {"show": True},
                "emphasis": {
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                },
            }
        ],
    }

    return st_echarts(option, height="500px", width="600px")


def plot_connectivity(ax, locality_id):
    # Load connectivity data and distance matrix
    df_dists = pd.read_excel(distances_file, index_col=0)
    df_connect = pd.read_excel(connectivity_file, index_col=0)

    # Sort by distance
    sorted_locality_ids = df_dists.loc[locality_id].sort_values().index[:10]

    # Re-order by distance to selected locality and plot
    df_connect = df_connect.loc[sorted_locality_ids, sorted_locality_ids]

    # Replace locality IDs by names in the truncated and sorted connectivity dataframe
    df_connect.index = df_locs.set_index("localityNo").loc[df_connect.index.values][
        "name"
    ]
    df_connect.columns = df_locs.set_index("localityNo").loc[df_connect.columns.values][
        "name"
    ]

    # Re-order by distance to selected locality and plot
    sns.heatmap(
        data=df_connect.where(df_connect > 0), vmin=0, vmax=100, cmap="crest", ax=ax
    )
    return 1


def showmap(start_coords):
    folium_map = leafmap.Map(
        location=start_coords,
        tiles="Cartodb dark_matter",
        control_scale=True,
        zoom_start=11,
    )

    folium_map.add_wms_layer(
        url="https://wms.geonorge.no/skwms1/wms.dybdedata2?",
        layers="Dybdedata2",
        transparent=True,
        control=True,
        overlay=True,
        format="image/png",
        name="Depth contours (GeoNorge)",
        shown=False,
    )

    # ESRI map background
    _ = folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satellite",
        overlay=False,
        show=False,
        control=True,
    ).add_to(folium_map)

    return folium_map


def add_particle_tracks_opendrift(
    filename, colors, line_styles, folium_map, locs_to_plot
):
    logging.info(f"Extracting Particle Tracks from '{filename}'")
    with xr.open_dataset(
        filename,
        engine="zarr",
        backend_kwargs={
            "storage_options": {
                "endpoint_url": "https://%s" % AWS_S3_ENDPOINT,
                "key": AWS_ACCESS_KEY_ID,
                "secret": AWS_SECRET_ACCESS_KEY,
                "token": AWS_SESSION_TOKEN,
            }
        },
    ) as ds:
        start_time = ds.time.values[0]
        end_time = ds.time.values[-1]
        for t in range(ds.lon.shape[0]):
            mask = ds.status.values[t, :] == 0
            origin = ds.origin_marker.values[t, 0]
            if origin not in locs_to_plot:
                continue
            # color = ['green', 'blue', 'black'][origin]
            color = colors[origin]
            line_style = line_styles.get(origin, "")
            alpha = 0.15 if line_style == "1" else 0.05
            locations = [
                (lat, lon)
                for lon, lat in zip(
                    ds.lon.values[t, :][mask], ds.lat.values[t, :][mask]
                )
            ]
            folium.vector_layers.PolyLine(
                locations, weight=2, color=color, dash_array=line_style, opacity=alpha
            ).add_to(folium_map)
    return start_time, end_time


def get_simulation_start_end_time(filename):
    logging.info(f"Checking '{filename}' for Simulation Start/Stop")
    with xr.open_dataset(
        filename,
        engine="zarr",
        backend_kwargs={
            "storage_options": {
                "endpoint_url": "https://%s" % AWS_S3_ENDPOINT,
                "key": AWS_ACCESS_KEY_ID,
                "secret": AWS_SECRET_ACCESS_KEY,
                "token": AWS_SESSION_TOKEN,
            }
        },
    ) as ds:
        start_time = ds.time.values[0]
        end_time = ds.time.values[-1]
    return start_time, end_time


#
# Logging
#
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s",
)
logging.Formatter.formatTime = (
    lambda self, record, datefmt=None: datetime.datetime.fromtimestamp(
        record.created, datetime.timezone.utc
    )
    .astimezone()
    .isoformat(sep="T", timespec="milliseconds")
)

#
# Page config
#
st.set_page_config(
    page_title="Iliad Aquaculture Smart Monitoring (Iliad pilot 07.01)",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": "https://www.sintef.no", "About": "# Test page."},
)

st.markdown(
    """
        <style>
               .block-container {
                    padding-top: 3rem;
                    padding-bottom: 3rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
        </style>
        """,
    unsafe_allow_html=True,
)


#
# Set up BarentsWatch API
# Load client id and password from .env file
logging.info("Retrieving Access Token for BarentsWatch...")
try:
    logging.info("Got Token for BarentsWatch")
    st.session_state["bw_token"] = get_token()
except:
    logging.error("Failed To Get Token to BarentsWatch")
    st.error(
        "Failed to get token for BarentsWatch. Not showing temperatures and lice count.",
        icon="🚨",
    )
    st.session_state["bw_token"] = ""

# connect to minio and test
# cf. https://stackoverflow.com/a/68543077/21124232
logging.info("Connecting to Minio...")
try:
    minio_client = Minio(
        endpoint=AWS_S3_ENDPOINT,
        access_key=AWS_ACCESS_KEY_ID,
        secret_key=AWS_SECRET_ACCESS_KEY,
        session_token=AWS_SESSION_TOKEN,
    )
    minio_client.list_buckets()
    logging.info("Connected to Minio")
except Exception as e:
    logging.critical("Minio Not Reachable")
    logging.critical(f"{e}")
    st.error("Minio Not Reachable. No Useful Data Available.", icon="🔥")

#
# Define data files
#
connectivity_s3 = f"s3://{AWS_BUCKET_NAME}/{AQUA_CONNECTIVITY_FILE_WITH_LOCALITY_ID_S3}"
simulation_file = f"s3://{AWS_BUCKET_NAME}/{AQUA_OPENDRIFT_OUTPUT_FILE_S3}"
localities_file = AQUA_SITE_FILE
distances_file = AQUA_SITE_DISTANCES_FILES

# load connectivity file
logging.info(f"Opening '{connectivity_s3}'")
bucket_name = connectivity_s3.split("//")[1].split("/")[0]
object_name = "/".join(connectivity_s3.split("//")[1].split("/")[1:])
response = minio_client.get_object(bucket_name, object_name)
connectivity_file = BytesIO(response.data)

norkyst_url = "https://thredds.met.no/thredds/fou-hi/norkyst800v2.html"
st.title("Iliad Aquaculture Mid-Norway Smart Monitoring")

# site layout two-columns, 70% / 30% of space
col1, col2 = st.columns([0.7, 0.3])

# column 1: map

# Default site
locality_name = "Tristeinen"
locality_id = 30560

# Load cached localities from file and create list/map of colors
closest_loc_ids, closest_loc_names = get_closest_sites(locality_id=locality_id, N=10)
colors = {
    name: color
    for name, color in zip(closest_loc_names, mpl.colors.TABLEAU_COLORS.values())
}

df_locs = (
    pd.read_excel(localities_file, index_col=0)
    .sort_values(by="name")
    .reset_index(drop=True)
)

# Write info from simulation
start_time, end_time = get_simulation_start_end_time(simulation_file)
start_time_fmt = pd.to_datetime(start_time).isoformat(timespec="minutes")
end_time_fmt = pd.to_datetime(end_time).isoformat(timespec="minutes")
fig, ax = plt.subplots(1, 2, figsize=(2 * 4, 4))
with col1:
    # Select site to show reported temperature over time
    initial_idx = int(df_locs[df_locs["name"] == locality_name].index.values[0])
    # Define a mapping from "name (localityId)" -> "localityId". This should ensure a unique mapping
    uniqname_locid_map = {
        f"{r['name']} ({r.localityNo})": r.localityNo for _, r in df_locs.iterrows()
    }
    # option = st.selectbox('Select site to update map and data', df_locs['name'], index=initial_idx)
    option = st.selectbox(
        "Select site to update map and data",
        list(uniqname_locid_map.keys()),
        index=initial_idx,
    )
    if option is not None:
        # locality_id = int(df_locs[df_locs['name'] == option]['localityNo'])
        # locality_name = str(df_locs[df_locs['name'] == option]['name'].values[0])
        locality_id = uniqname_locid_map[option]
        locality_name = str(
            df_locs[df_locs["localityNo"] == locality_id]["name"].values[0]
        )

        # Load cached localities from file and update list/map of colors
        closest_loc_ids, closest_loc_names = get_closest_sites(
            locality_id=locality_id, N=10
        )
        colors = {
            name: color
            for name, color in zip(closest_loc_ids, mpl.colors.TABLEAU_COLORS.values())
        }

        # st.write(option, locality_id)
        df_temp = get_site_temperature(locality_id, 2023, st.session_state["bw_token"])
        df_lice = get_site_licecount(locality_id, 2023, st.session_state["bw_token"])
        if df_temp.dropna().size > 0:
            # f'{locality_name}, 2023'
            df_temp.plot(
                x="week",
                y="seaTemperature",
                ax=ax[0],
                c=colors[locality_id],
                label="Temperature",
            )
            ax2 = ax[0].twinx()
            df_lice.plot(
                x="week",
                y="avgAdultFemaleLice",
                ax=ax2,
                c=colors[locality_id],
                ls="--",
                label="Lice count",
            )
            ax[0].set_ylabel("Sea temperature ($^\\circ$C)")
            ax[0].legend(
                loc="lower left", bbox_to_anchor=[0, 0.1]
            ).get_frame().set_linewidth(0)
            ax2.legend(loc="lower left").get_frame().set_linewidth(0)
            ax2.set_ylabel("Average adult female lice count")
            ax2.set_ylim(bottom=0)
            ax[0].set_ylim(bottom=0)
            ax[0].set_xlabel("Week number")
            ax[0].set_title(f"{locality_name}\n (Line color matches map below)")

            # Mark current week number
            ax[0].axvline(datetime.datetime.now().isocalendar()[1], c="k")
        else:
            ax[0].text(0.5, 0.5, "No data", ha="center", va="center")

# column 2: text

with col2:
    st.write(
        ":orange[Disclaimer: This pilot is for demonstration of a twin-like application for Smart Monitoring of environmental conditions that affect aqauaculture operations, there may be inaccuracies in datasets and visualizations due to simplification. Current simulations are based on surface water.]"
    )
    st.write(
        f"In this twin application, you can study the potential for water contact between aquaculture sites that indicates the possibility for infection based on particle transport in surface waters between aquaculture sites. The underlying ocean model is [NorKyst800]({norkyst_url}) with forecast data (+24 hours), and the underlying transport model is [OpenDrift](https://opendrift.github.io/).  Sea temperatures and lice counts are reported numbers retrieved from [BarentsWatch](https://www.barentswatch.no/artikler/apnedata/).  Dashed lines in the map indicate the site is currently listed as fallow."
    )

    st.write(f"Simulation start time: {start_time_fmt}")
    st.write(f"Simulation end time: {end_time_fmt}")


# Show connectivity figure and temperature for selected site
with col2:
    plot_connectivity(ax=ax[1], locality_id=locality_id)
    ax[1].set_title("Potential site connectivity")
    ax[1].set_ylabel("")
    fig.tight_layout()
    st.pyplot(fig)

#
# Create Folium map
#
folium_map = showmap(
    [
        float(df_locs.set_index("localityNo").loc[locality_id, "lat"]),
        float(df_locs.set_index("localityNo").loc[locality_id, "lon"]),
    ]
)

# Get basic site info
year_now, week_now, _ = datetime.datetime.now().isocalendar()
df_sites_info = get_sites_info(week_now, year_now, st.session_state["bw_token"])

# Add transport trajectories from each site
colors_locs = {
    locid: color
    for locid, color in zip(closest_loc_ids, mpl.colors.TABLEAU_COLORS.values())
}
line_styles = {
    locid: "10" if row["isFallow"] else "1" for locid, row in df_sites_info.iterrows()
}
start_time, end_time = add_particle_tracks_opendrift(
    simulation_file,
    colors=colors_locs,
    line_styles=line_styles,
    folium_map=folium_map,
    locs_to_plot=closest_loc_ids,
)

# Add localities markers
for _, row in df_locs.iterrows():
    name = row["name"]
    locid = row["localityNo"]
    if locid in closest_loc_ids:
        color = colors[locid]
        radius = 10
    else:
        color = "gray"
        radius = 5

    loc = [row["lat"], row["lon"]]
    # folium.Marker(location=loc, tooltip=name,
    #              icon=folium.Icon(color=colors[name], icon='eye-open')).add_to(folium_map)
    popup = f'<b>Site: </b>{row["name"]}<br>'
    popup += f'<b>Site number: </b>{row["localityNo"]}<br>'
    popup += f'<b>Longitude: </b>{row["lon"]}<br><b>Latitude: </b>{row["lat"]}<br>'
    # popup += f'<b>Latest lice count: </b>{row["avgAdultFemaleLice"]}<br>'
    folium.CircleMarker(
        location=loc,
        tooltip=name,
        radius=radius,
        color=color,
        popup=folium.Popup(popup, parse_html=False, max_width="200"),
        fill=True,
    ).add_to(folium_map)

with col1:
    # Add Folium map to Streamlit
    folium_map.to_streamlit()

    plot_connectivity_echarts(locality_id=locality_id)
