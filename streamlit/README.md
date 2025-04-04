# Aquaculture Site Connectivity, Streamlit Component

## Prerequisites

1. Configure your BarentsWatch credentials

```sh
$ cat ./.env
BW_CLIENT_ID=
BW_CLIENT_SECRET=
[...]
``` 

See also https://developer.barentswatch.no/docs/tutorial.

2. Configure your S3 credentials to access aquaculture site data, cf.

```sh
$ cat ./.env
[...]
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
AWS_S3_ENDPOINT=
AWS_DEFAULT_REGION=
AWS_BUCKET_NAME=
[...]
``` 

3. Configure where to acccess simulation outputs

```sh
$ cat ./.env
[...]
AQUA_CONNECTIVITY_FILE_WITH_LOCALITY_ID_S3=aquaculture/salmon_midnor_connectivity_withLocalityId.xlsx
AQUA_OPENDRIFT_OUTPUT_FILE_S3=aquaculture/salmon_midnor_test.zarr
AQUA_SITE_FILE=https://iliadmonitoringtwin.blob.core.windows.net/public-data/salmon-sites-midnorway.xlsx
AQUA_SITE_DISTANCES_FILES=https://iliadmonitoringtwin.blob.core.windows.net/public-data/sites-atsea-salmonoids-midnor-distances.xlsx
```

See also `./.env_example` for a full example of the configuration file.

## Running on Bare Metal

### Setup

```sh
$ mamba create --name iliad-aquaculture-streamlit python=3.12
$ mamba activate iliad-aquaculture-streamlit
$ pip install -r requirements.txt
```

### Running

```sh
$ mamba activate iliad-aquaculture-opendrift
$ streamlit run app/main.py --server.headless true
```

## Running on Docker

Build:

```sh
$ docker build --tag iliad-aquaculture-streamlit .
```

Run:

```sh
$ docker run --interactive \
    --env-file ./.env \
    --tty \
    --publish 14858:14858 \
    iliad-aquaculture-streamlit
```

Then you can access the frontend in the browser at [http://localhost:1458](http://localhost:1458).

# Contact & Blame

- Volker Hoffmann (volker.hoffmann@sintef.no)
- Raymond Nepstad (raymond.nepstad@sintef.no)
