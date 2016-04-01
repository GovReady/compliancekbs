# generate/update the sample yaml files for the 18f docs

import os.path
import re
import rtyaml
from collections import OrderedDict
import urllib.request

for controlid in ("AC", "AT", "AU", "CA", "CM", "CP", "IA", "IR", "PL", "PS", "RA", "SA", "SC", "SI"):
    fn = "resources/documents/" + "18f-policy-" + controlid + ".yaml"

    # update files that already have content, don't touch fields we don't write
    if not os.path.exists(fn):
        doc = OrderedDict()
    else:
        with open(fn,) as f:
            doc = rtyaml.load(f.read()) or OrderedDict()

    doc["type"] = "policy-document"
    doc["id"] = "18f-policy-" + controlid

    md = urllib.request.urlopen("https://raw.githubusercontent.com/18F/compliance-docs/master/%s-Policy.md" % controlid).read().decode("utf8")

    doc["title"] = re.match("#\s+(.*)", md).group(1)
    doc["owner"] = "18F"
    doc["url"] = "https://github.com/18F/compliance-docs/blob/master/%s-Policy.md" % controlid
    doc["authoritative-url"] = "https://raw.githubusercontent.com/18F/compliance-docs/master/%s-Policy.md" % controlid
    doc["format"] = "markdown"

    with open(fn, "w") as f:
        f.write(rtyaml.dump(doc))
