FROM ubuntu:15.10
MAINTAINER Fen Labalme <fen@civicactions.com>

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    python3 python3-dev python3-pip \
    sqlite3 htmldoc poppler-utils

# Get pip to download and install requirements:
COPY requirements.txt /opt/
RUN pip3 install -r /opt/requirements.txt

# Expose port 8000:
EXPOSE 8000

# Copy the application folder inside the container:
COPY . /opt/compliancekbs
WORKDIR /opt/compliancekbs

CMD ["python3","server.py"]
