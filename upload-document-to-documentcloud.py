# Uploads a document to DocumentCloud using their API.
#
# usage:
#
# python3 upload-to-documentcloud.py resource-id
#
# The resource-id corresponds to the name of a resource file
# in resources/documents. The PDF will be fetched from the
# URL specified in the authoritative-url field in the YAML
# file.
#
# If the document has already been uploaded to DocumentCloud,
# its metadata on DocumentCloud (currently just title) is updated.

import sys, os

import rtyaml
from documentcloud import DocumentCloud

from server import get_documentcloud_document_id

# Command line args

if len(sys.argv) < 2:
    print("Usage: python3 upload-to-documentcloud.py resource-id")
    sys.exit(1)

resource_id = sys.argv[1]

# Get DocumentCloud credentials and create API client object.
creds = { }
for line in open("documentcloud.ini"):
    key, value = line.strip().split("=", 1)
    creds[key] = value

documentcloud = DocumentCloud(creds['DOCUMENTCLOUD_USERNAME'], creds['DOCUMENTCLOUD_PASSWORD'])

# Open the existing YAML file.

fn = os.path.join("resources", "documents", resource_id + ".yaml")
with open(fn) as f:
    res = rtyaml.load(f)

# Is it a PDF?

if res.get("format") != "pdf":
    print("Not a PDF resource.")
    sys.exit(1)

# Already in DocumentCloud?

dcid = get_documentcloud_document_id(res)
if dcid:
    print("Document is already uploaded to DocumentCloud!")
    print(res['url'])

    doc = documentcloud.documents.get("-".join(dcid))
    print(doc.id)
    print(doc.title)

    if doc.canonical_url != res['url']:
        print("URL stored in YAML does not match DocumentCloud canonical_url:")
        print(doc.canonical_url)

    if doc.title != res['title']:
        print("Updating title...")
        doc.title = res['title']
        doc.save()

    print(doc.small_image_url)

    sys.exit(0)

# Get the URL to the PDF.

url = res['authoritative-url']

# DocumentCloud's upload API gets confused if it's passed a URL that redirects.
# Use urllib.request.urlopen to resolve the redirect.
import urllib.request
url = urllib.request.urlopen(url).geturl()

# Upload to DocumentCloud.

doc = documentcloud.documents.upload(
    url,
    title=res.get('title'),
    access="public")

# Update YAML.

res['url'] = doc.canonical_url

with open(fn, "w") as f:
    f.write(rtyaml.dump(res))

print("Done.")
