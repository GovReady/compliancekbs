# Create & save a YAML file for an HTML document given a URL.
#
# usage:
#
# python3 create-html-document-yaml.py resource-id http://url/to/html
#
# You choose the resource-id. It goes into the file name 
# (resources/documents/{resource-id}.yaml) and the YAML's
# id field.

import sys, io, collections, os.path
import urllib.request

import rtyaml
import PyPDF2
from bs4 import BeautifulSoup

# Command line args

if len(sys.argv) < 3:
	print("Usage: python3 create-html-yaml.py resource-id http://url/to/html")
	sys.exit(1)

resource_id, html_url = sys.argv[1:3]

# Fetch PDF.
# Wrap the urlib.request data in a BytesIO to make it seekable.
# pdf = PyPDF2.PdfFileReader(io.BytesIO(urllib.request.urlopen(html_url).read()))
# Fetch HTML.
# Wrap the urlib.request data in a BytesIO to make it seekable.
soup = BeautifulSoup(urllib.request.urlopen(html_url).read(), 'html.parser')

# Build YAML.

data = collections.OrderedDict()

data["id"] = resource_id
data["type"] = "authoritative-document or policy-document --- change this!"

if soup.title:
	data["title"] = str(soup.title.string)

# if "/Subject" in pdf.documentInfo:
# 	data["alt-titles"] = [str(pdf.documentInfo["/Subject"])]

data["owner"] = None # for user to fill in

data["url"] = html_url # should be updated if document is copied into Document Cloud
data["authoritative-url"] = html_url
data["format"] = "html"

# Save.

fn = os.path.join("resources", "documents", resource_id + ".yaml")
print("Writing", fn, "...")
with open(fn, 'w') as f:
	f.write(rtyaml.dump(data))
print("Don't forget to update the 'type' field and make sure the other fields are OK.")

