import os
import pprint
from datetime import datetime, timedelta
from typing import Dict

import click
import fsspec
import pandas as pd
import pyproj
import toml
import xarray as xr
from dotenv import load_dotenv
from minio import Minio
from opendrift.models.sedimentdrift import OceanDrift
from opendrift.readers import reader_netCDF_CF_generic
from tqdm import tqdm

load_dotenv()

OPENDRIFT_LOGLEVEL = 20  # Info output (0: debug, 50: no output)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")


def _load_config_from_env() -> Dict:
    config = {
        "sitedata": {
            "site_file": os.getenv("AQUA_SITE_FILE"),
            "sites_distances_file": os.getenv("AQUA_SITE_DISTANCES_FILES"),
        },
        "opendrift": {
            "particles_per_site": int(os.getenv("AQUA_OPENDRIFT_PARTICLES_PER_SITE")),
            "simulation_duration_hours": int(
                os.getenv("AQUA_OPENDRIFT_SIMULATION_DURATION_HOURS")
            ),
            "output_file": os.getenv("AQUA_OPENDRIFT_OUTPUT_FILE"),
            "output_file_s3": "s3://%s/%s"
            % (AWS_BUCKET_NAME, os.getenv("AQUA_OPENDRIFT_OUTPUT_FILE_S3")),
        },
        "connectivity": {
            "number_of_neighbours": int(
                os.getenv("AQUA_CONNECTIVITY_NUMBER_OF_NEIGHBOURS")
            ),
            "radius": int(os.getenv("AQUA_CONNECTIVITY_RADIUS")),
            "output_file": os.getenv("AQUA_CONNECTIVITY_OUTPUT_FILE"),
            "output_file_withLocalityId": os.getenv(
                "AQUA_CONNECTIVITY_OUTPUT_FILE_WITH_LOCALITY_ID"
            ),
            "output_file_s3": "s3://%s/%s"
            % (AWS_BUCKET_NAME, os.getenv("AQUA_CONNECTIVITY_OUTPUT_FILE_S3")),
            "output_file_withLocalityId_s3": "s3://%s/%s"
            % (
                AWS_BUCKET_NAME,
                os.getenv("AQUA_CONNECTIVITY_OUTPUT_FILE_WITH_LOCALITY_ID_S3"),
            ),
        },
    }
    return config


def run_opendrift(config, df_locs, starttime):
    """Run OpenDrift forecast from all localities"""

    # Initialize opendrift model
    o = OceanDrift(
        loglevel=OPENDRIFT_LOGLEVEL
    )  # Set loglevel to 0 for debug information

    # Norkyst ocean model for current
    norkyst_agg = "https://thredds.met.no/thredds/dodsC/sea/norkyst800m/1h/aggregate_be"
    reader_norkyst = reader_netCDF_CF_generic.Reader(norkyst_agg)

    # Configure model
    o.add_reader(
        reader_norkyst,
        variables=["x_sea_water_velocity", "y_sea_water_velocity", "x_wind", "y_wind"],
    )
    o.set_config("environment:fallback:x_sea_water_velocity", 0)
    o.set_config("environment:fallback:y_sea_water_velocity", 0)
    o.set_config("drift:horizontal_diffusivity", 1)
    o.set_config("general:coastline_action", "previous")

    # Seed at all localities
    for _, row in df_locs.iterrows():
        lon_ = row["lon"]
        lat_ = row["lat"]
        o.seed_elements(
            lon=lon_,
            lat=lat_,
            radius=10,
            number=config["particles_per_site"],
            origin_marker=row["localityNo"],
            time=starttime,
        )

    # Run model
    o.run(
        duration=timedelta(hours=config["simulation_duration_hours"]),
        time_step=600,
        time_step_output=600,
        outfile=config["output_file"],
    )


def calculate_distance_connectivity_nearest(
    ncfile, df_sites, df_dists, min_dist, num_sites=10, particles_per_site=100
):
    """Calculate simple connectivity between sites, only consider 10 closest sites to each

    Approach: count number of trajectories that pass within a radius of each site.
              Normalize by total tractories, return % values.
    """

    names = df_sites.set_index("localityNo")["name"]

    df_connect = pd.DataFrame(
        index=df_sites.localityNo, columns=df_sites.localityNo, dtype="float"
    )
    df_connect[:] = 0
    geod = pyproj.Geod(ellps="WGS84")

    with xr.open_dataset(ncfile) as ds:
        for _, row in tqdm(df_sites.iterrows(), total=df_sites.shape[0]):

            # Get N nearest sites
            nearest_ids = (
                df_dists[row["localityNo"]]
                .sort_values(ascending=True)
                .index[:num_sites]
            )
            lons = [row["lon"]] * ds.lon.shape[1]
            lats = [row["lat"]] * ds.lon.shape[1]

            # Iterate trajecory, determine overlap with current bound, determine origin
            for t in range(ds.lon.shape[0]):
                origin = ds.origin_marker.values[t, 0]
                if not (origin in nearest_ids):
                    continue
                dists = geod.inv(lons, lats, ds.lon.values[t, :], ds.lat.values[t, :])[
                    2
                ]

                # Add 1 to this site-origin if any trajectory passes closer than min_dist
                df_connect.loc[row["localityNo"], origin] += (dists < min_dist).max()

    # Normalize (convert to %)
    df_connect = 100 * df_connect / particles_per_site

    return df_connect


def _replace_headers_in_connectivity_dataframe_num2name(
    df_connectivity: pd.DataFrame, df_localities: pd.DataFrame
) -> pd.DataFrame:
    """for a connectivity dataframe with indices/columns are site IDs, change them the indices/
    columns the site names"""
    new_index_dict = {}
    for _, row in df_localities.iterrows():
        new_index_dict[row["localityNo"]] = row["name"]
    dfx = df_connectivity.copy()
    dfx.rename(columns=new_index_dict, inplace=True)
    dfx.rename(index=new_index_dict, inplace=True)
    dfx.rename_axis("name", axis=0, inplace=True)
    dfx.rename_axis("name", axis=1, inplace=True)
    return dfx


def _upload_trajectories_to_s3(output_file_netcdf: str, output_file_s3: str) -> None:
    print("*** Uploading Trajectories to S3")
    print(f"Opening '{output_file_netcdf}...")
    ds_trajectories = xr.open_dataset(output_file_netcdf)
    print(f"Connecting to 'https://{AWS_S3_ENDPOINT}'...")
    fs = fsspec.filesystem(
        "s3",
        endpoint_url="https://%s" % AWS_S3_ENDPOINT,
        key=AWS_ACCESS_KEY_ID,
        secret=AWS_SECRET_ACCESS_KEY,
        token=AWS_SESSION_TOKEN,
    )
    print(f"Writing trajectories to '{output_file_s3}'...")
    # mapper = fs.get_mapper("s3://oidc-volkerh/aquaculture/salmon_midnor_test.zarr")
    mapper = fs.get_mapper(output_file_s3)
    # !!! here be dragons ~ https://github.com/fsspec/s3fs/issues/931
    try:
        ds_trajectories.to_zarr(mapper, compute=True, mode="w")
        print("*** Done Uploading Trajectories to S3")
    except Exception as e:
        print(f"Upload error: {e}")


def _upload_connectivity_to_s3(output_file_local: str, output_file_s3: str) -> None:
    minio_client = Minio(
        endpoint=AWS_S3_ENDPOINT,
        access_key=AWS_ACCESS_KEY_ID,
        secret_key=AWS_SECRET_ACCESS_KEY,
        session_token=AWS_SESSION_TOKEN,
    )
    bucket_name = output_file_s3.split("//")[1].split("/")[0]
    object_name = "/".join(output_file_s3.split("//")[1].split("/")[1:])
    print(f"Uploading '{object_name}' to '{output_file_local}'")
    try:
        minio_client.fput_object(bucket_name, object_name, output_file_local)
        print(f"File '{output_file_local}' uploaded successfully as '{object_name}'")
    except Exception as e:
        print(f"Upload error: {e}")
    pass


@click.command()
@click.option(
    "--starttime",
    help="Start time of simulation",
    default=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    type=click.DateTime(),
)
def run(starttime):
    # Load config
    config = _load_config_from_env()
    pprint.pp(config)

    # Load positions for sites nearest to Tristeinen
    df_locs = pd.read_excel(config["sitedata"]["site_file"])
    df_dists = pd.read_excel(config["sitedata"]["sites_distances_file"], index_col=0)

    print(f"Running model, start time: {starttime}")
    run_opendrift(config["opendrift"], df_locs, starttime)

    # Calculate and store connectivity matrix
    print("Calculate connectivity matrix")
    # df_connect = calculate_simple_connectivity(OUTFILE, df_locs)
    df_connect = calculate_distance_connectivity_nearest(
        config["opendrift"]["output_file"],
        df_locs,
        df_dists,
        min_dist=config["connectivity"]["radius"],
        num_sites=config["connectivity"]["number_of_neighbours"],
        particles_per_site=config["opendrift"]["particles_per_site"],
    )
    # (opt) write a connectivity matrix that has localityNo instead of site names as headers
    if "output_file_withLocalityId" in config["connectivity"].keys():
        df_connect.to_excel(config["connectivity"]["output_file_withLocalityId"])
    df_connect = _replace_headers_in_connectivity_dataframe_num2name(
        df_connect, df_locs
    )
    df_connect.to_excel(config["connectivity"]["output_file"])

    # upload trajectories to edito/minio
    _upload_trajectories_to_s3(
        config["opendrift"]["output_file"], config["opendrift"]["output_file_s3"]
    )

    # upload connectivity files to edito/minio
    _upload_connectivity_to_s3(
        config["connectivity"]["output_file"], config["connectivity"]["output_file_s3"]
    )
    if "output_file_withLocalityId" in config["connectivity"].keys():
        _upload_connectivity_to_s3(
            config["connectivity"]["output_file_withLocalityId"],
            config["connectivity"]["output_file_withLocalityId_s3"],
        )

    print("--- ALL DONE ---")


if __name__ == "__main__":
    run()
