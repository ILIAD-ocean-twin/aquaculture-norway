FROM opendrift/opendrift:latest
# opendrift image is built on top of micromamaga image
# this image uses the user mambauser
# cf. https://github.com/OpenDrift/opendrift/blob/master/Dockerfile
# cf. https://github.com/mamba-org/micromamba-docker/blob/main/debian.Dockerfile
# so we need to install python packages as this user
USER mambauser
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# now do the rest
WORKDIR /aquaculturedemo
RUN mkdir -p /aquaculturedemo/modeloutput
COPY runnorkystforecast.py ./
CMD ["python", "runnorkystforecast.py"]
