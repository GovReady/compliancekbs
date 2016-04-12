# Create & save a YAML file for a PDF document given a URL.
#
# usage:
#
# pip3 install pyPDF2
# python3 create-document-yaml.py resource-id http://url/to/pdf
#
# You choose the resource-id. It goes into the file name 
# (resources/documents/{resource-id}.yaml) and the YAML's
# id field.

import sys, io, collections, os.path
import urllib.request

import rtyaml
import PyPDF2

# Command line args

if len(sys.argv) < 3:
	print("Usage: python3 create-document-yaml.py resource-id http://url/to/pdf")
	sys.exit(1)

resource_id, pdf_url = sys.argv[1:3]

# Fetch PDF.
# Wrap the urlib.request data in a BytesIO to make it seekable.
pdf = PyPDF2.PdfFileReader(io.BytesIO(urllib.request.urlopen(pdf_url).read()))

# Build YAML.

data = collections.OrderedDict()

data["id"] = resource_id
data["type"] = "authoritative-document or policy-document --- change this!"

if "/Title" in pdf.documentInfo:
	data["title"] = str(pdf.documentInfo["/Title"])

if "/Subject" in pdf.documentInfo:
	data["alt-titles"] = [str(pdf.documentInfo["/Subject"])]

data["owner"] = None # for user to fill in

data["url"] = pdf_url # should be updated if document is copied into Document Cloud
data["authoritative-url"] = pdf_url
data["format"] = "pdf"

# Save.

fn = os.path.join("resources", "documents", resource_id + ".yaml")
print("Writing", fn, "...")
with open(fn, 'w') as f:
	f.write(rtyaml.dump(data))
print("Don't forget to update the 'type' field and make sure the other fields are OK.")

