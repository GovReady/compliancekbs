FROM ubuntu:15.10
MAINTAINER Fen Labalme <fen@civicactions.com>

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    python3 python3-dev python3-pip \
    sqlite3 htmldoc poppler-utils

# other tools we likely don't need
#   tar git curl wget dialog net-tools build-essential \

# Copy the application folder inside the container
COPY requirements.txt /opt/

# Get pip to download and install requirements:
RUN pip3 install -r /opt/requirements.txt

# Expose ports
EXPOSE 80

WORKDIR /opt/compliancekbs

CMD ["python3 server.py"]
