# ILIAD Aquaculture

![Frontend screenshot](screenshots/streamlit.png?raw=true)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This repository contains the source code of the Norwegian ILIAD aquaculture pilot.

The pilot is meant to be deployed on the [EDITO Datalab](https://datalab.dive.edito.eu) platform.

It can also be deployed on any infrastructure capable of running Docker (or Python). Data is exchanged through S3 compatible object storage. We suggest [Minio](https://min.io).

## Architecture

The pilot consists of three components:

1. A Jupyter notebook (`notebooks/get_sites_from_barentswatch.ipynb`) that downloads aquaculture site data from [Barentswatch](https://www.barentswatch.no). The notebook outputs an Excel table with site locations and an Excel table with the distance matrix.
2. A script (`opendrift/runnorkystforecast.py`) that runs (i) [OpenDrift](https://opendrift.github.io), and (ii) calculates the connectivity matrix for nearby aquaculture sites. The script outputs trajectories from OpenDrift and the  connectivity matrix between sites. OpenDrift uses the [Norkyst800](https://thredds.met.no/thredds/fou-hi/fou-hi.html) ocean model.
3. A Streamlit frontend (`streamlit/app/main.py`) that loads and the trajectories from OpenDrift, the connectivity matrix, as well as supplementary information from Barentswatch.

The OpenDrift and Streamlit components are wrapped into Docker containers.

For more details, see `opendrift/README.md` and `streamlit/README.md`.

## Quickstart (on EDITO Datalab)

1. Make sure you have an account on the [EDITO Datalab](https://datalab.dive.edito.eu).
2. Sign up and create [credentials for Barentswatch](https://developer.barentswatch.no/docs/tutorial).
3. Run the notebook in `notebooks/get_sites_from_barentswatch.ipynb` to generate `salmon-sites-midnorway.xlsx` and `sites-atsea-salmonoids-midnor-distances.xlsx`
4. Create a folder `aquaculture` under *My Files* on the EDITO Datalab.
5. Upload the `salmon-sites-midnorway.xlsx` and `sites-atsea-salmonoids-midnor-distances.xlsx` into the `aquaculture` folder under *My Files* on the EDITO Datalab.
6. On EDITO Datalab, find the process `iliad-aquaculture-opendrift` and run it once.
7. On EDITO Datalab, find the process `iliad-aquaculture-streanlit` and launch it.

## Funding

This work was supported by EU Horizon 2020 Research and Innovation Programme under Grant Agreement No 101037643 (project [ILIAD](https://ocean-twin.eu)).

## Contact

- Raymond Nepstad (raymond.nepstad@sintef.no)
- Volker Hoffmann (volker.hoffmann@sintef.no)
- Antoine Pultier (antoine.pultier@sintef.no)
