# Build the docker container with ubuntu 15.10, python3 & flask.
docker build -t compliancekbs .

# Run the container on localhost:8000
docker run -dit -p 8000:8000 --name compliancekbs compliancekbs

# Enter the container:
# docker run -ti compliancekbs bash
