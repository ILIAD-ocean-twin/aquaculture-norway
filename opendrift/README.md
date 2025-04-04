# Aquaculture Site Connectivity with OpenDrift

## Prerequisities

1. You need to configure the simulation, cf.

```sh
$ cat ./.env
AQUA_SITE_FILE=https://iliadmonitoringtwin.blob.core.windows.net/public-data/salmon-sites-midnorway.xlsx
AQUA_SITE_DISTANCES_FILES=https://iliadmonitoringtwin.blob.core.windows.net/public-data/sites-atsea-salmonoids-midnor-distances.xlsx
AQUA_OPENDRIFT_PARTICLES_PER_SITE=1
AQUA_OPENDRIFT_SIMULATION_DURATION_HOURS=1
AQUA_OPENDRIFT_OUTPUT_FILE=modeloutput/salmon_midnor_test.nc
AQUA_OPENDRIFT_OUTPUT_FILE_S3=aquaculture-dev/salmon_midnor_test.zarr
AQUA_CONNECTIVITY_NUMBER_OF_NEIGHBOURS=10
AQUA_CONNECTIVITY_RADIUS=100
AQUA_CONNECTIVITY_OUTPUT_FILE=modeloutput/salmon_midnor_connectivity.xlsx
AQUA_CONNECTIVITY_OUTPUT_FILE_S3=aquaculture-dev/salmon_midnor_connectivity.xlsx
AQUA_CONNECTIVITY_OUTPUT_FILE_WITH_LOCALITY_ID=modeloutput/salmon_midnor_connectivity_withLocalityId.xlsx
AQUA_CONNECTIVITY_OUTPUT_FILE_WITH_LOCALITY_ID_S3=aquaculture-dev/salmon_midnor_connectivity_withLocalityId.xlsx
[...]
```

2. If you want to upload outputs to an S3 compatible storage, set appropriate environment variables, cf.

```sh
$ cat ./.env
[...]
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
AWS_S3_ENDPOINT=
AWS_DEFAULT_REGION=
AWS_BUCKET_NAME=
```

See also `./.env_example` for a full example of the configuration file.

## Running on Bare Metal

### Setup

```sh
$ mamba create --name iliad-aquaculture-opendrift python=3.11
$ mamba activate iliad-aquaculture-opendrift
$ mamba install opendrift
```

For more details, refer to https://opendrift.github.io/install.html.

### Running

```sh
$ mamba activate iliad-aquaculture-opendrift
$ python runnorkystforecast.py --help
```

## Running on Docker

### Amd64 (linux/amd64)

Build:

```sh
$ docker build --tag iliad-opendrift .
```

Run:

```sh
$ docker run --interactive \
    --env-file=./.env \
    --platform linux/amd64 \
    --tty \
    --mount type=bind,src=`pwd`/modeloutput2,dst=/aquaculturedemo/modeloutput \
    iliad-opendrift 
```

If you skip the `--mount` part, the output files are written into the container only and will be deleted when the container exists. This is fine if you upload them to object storage.

### Arm64 (linux/arm64/v8)

You will need to make sure you can cross-build Dockers images onto another architecture. On Mac, you can use [Rancher Desktop](https://rancherdesktop.io), for example.

Build:

```sh
$ docker buildx build --platform linux/amd64 --tag iliad-opendrift .
```

Run:

```sh
$ docker run --interactive \
    --env-file=./.env \
    --tty \
    --mount type=bind,src=`pwd`/modeloutput2,dst=/aquaculturedemo/modeloutput \
    iliad-opendrift 
```

If you skip the `--mount` part, the output files are written into the container only and will be deleted when the container exists. This is fine if you upload them to object storage.

# References

- https://github.com/OpenDrift/opendrift

# Contact & Blame

- Volker Hoffmann (volker.hoffmann@sintef.no)
- Raymond Nepstad (raymond.nepstad@sintef.no)
