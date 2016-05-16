#!/usr/bin/env bash

apt-get update

# install pip for python 3
curl -O https://bootstrap.pypa.io/get-pip.py
sudo python3 get-pip.py

# remove get-pip.py file since we installed pip
rm get-pip.py

# install git
sudo apt-get install git -y

# install repo
# git clone https://github.com/GovReady/compliancekbs.git

# install a few needed libraries
sudo apt-get install sqlite3 htmldoc poppler-utils -y

# install requirements for our kbs flask app
sudo pip3 install -r requirements.txt