# Build the docker container with ubuntu 15.10, python3 & flask.
docker build -t compliancekbs .

# Run the container.
docker run -dit -v .:/opt/compliancekbs --name compliancekbs compliancekbs

# Visit: http://localhost:8088

# Enter the container:
# docker run -ti compliancekbs bash