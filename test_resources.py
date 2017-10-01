#
# This is the start of script to test resource files are error free
# Errors will happen if documents are not proper yaml files or 'title' key is missing.
#
# Usage:
#   python3 test_resources.py

import os
import yaml

dir_path = os.path.dirname(os.path.realpath(__file__))
document_dir = "/resources/documents"

listing = os.listdir(dir_path+document_dir)

# print("listing: {}".format(listing))

for infile in listing:
    print("current file is: {}".format(infile))
    filename = dir_path+document_dir+"/"+infile
    print("test yaml {}".format(filename))
    with open(filename, 'r') as stream:
        data_loaded = yaml.load(stream)
        print("id: {}".format(data_loaded['id']))
        print("title: {}".format(data_loaded['title']))
