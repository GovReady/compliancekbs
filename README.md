# compliancekbs
Compliance Knowledge Base Service for Security Controls Compliance Server

![Screenshot of Compliance Knowledge Base Service](/static/compliancekbs-sreenshot.png?raw=true "Screenshot of Compliance Knowledge Base Service")

API server
----------

The API server requires python3 and some dependencies:

	sudo apt-get install sqlite3 htmldoc poppler-utils
    pip3 install -r requirements.txt

(`htmldoc` and `poppler-utils` are used for generating thumbnails of Markdown documents (HTML=>PDF and then PDF=>image).)

Then start using:

    python3 server.py

Or in production:

	sudo ./run

The process must be killed and restarted if any resource (document) files are added/changed --- i.e. the files are loaded into memory at program start and the process isn't monitoring for changes in the files.

The server logs queries to an sqlite database. To get the log, run:

	sqlite3 -csv access_log.db "select * from query_log" > access_log.csv

The columns are the date/time of the query (in UTC), the user's IP address, the user's query, a space-separated list of document IDs that were returned by the query (in the order in which they were returned), and the execution duration of the query in milliseconds.


Other tools
-----------

A few additional scripts are here:

* `create-document-yaml.py` downloads a PDF, extracts some of its metadata, and creates a new YAML file for it using a new resource ID that you provide. You must go into the YAML file and change its `type` field to the right value afterwards.

* `upload-document-to-documentcloud.py` takes a resource ID and uploads that document to DocumentCloud, and updates the YAML by setting the `url` field to the DocumentCloud URL. Or if the YAML already has a `url` that is pointing to DocumentCloud, the DocumentCloud metadata for the document is updated based on the content of the YAML file.

* `text-analysis.py` performs a text analysis to find interesting phrases in a document. When run without command-line arguments, extracts phrases from all documents. Or, specify a resource ID to extract phrases from that document and update the YAML file, appending new terms to the end.

The text analysis script has an additional dependency that you must fetch this way:

	python3 -m nltk.downloader punkt

The DocumentCloud uploader script requires that you create a file named `documentcloud.ini` with:

	DOCUMENTCLOUD_USERNAME=yourusername
	DOCUMENTCLOUD_PASSWORD=yourpassword

The workflow for creating a new document YAML file is:

	python3 create-document-yaml.py nist-sp-800-145 http://dx.doi.org/10.6028/NIST.SP.800-145
	python3 upload-document-to-documentcloud.py nist-sp-800-145
	python3 text-analysis.py nist-sp-800-145

where `nist-sp-800-145` is a new resource ID that you assign. In the first command, a URL to the PDF for the document is given.


YAML schema
-----------

YAML files describe either documents or roles.

### document

A YAML file may describe a document. Documents have the following fields:

`id`: An identifier for this document unique within the GovReady Compliance Knowledge Base. This `id` is used within term references (see below) to refer to this document from other documents. Therefore if an `id` is ever changed, it must also be changed in *all* other documents that refer to this document.

`type`: Either `authoritative-document` for a law, regulation, or other similar document (e.g., NIST documents) or `policy-document` for a policy implementation by an agency (e.g., 18F and CMS documents).

`owner`: Display text for who authored the document (e.g. `NIST`, `CMS`, `18F`). (In the future we'll turn this into an identifier of some sort of resource.)

`title`: The display title of the document.

`alt-titles`: A list of alternate titles of the document.

`short-title`: A short form display title of the document.

`url`: The preferred URL where the document can be viewed. This is a link for humans. We recognize URLs that look like `https://www.documentcloud.org/documents/###-____.html` for displaying thumbnails from DocumentCloud. All documents must have a `url`.

`authoritative-url`: A link to the authoritative copy of a document, i.e. as published by the document owner. The URL should return a direct download link for a file in the format given in the `format` document property. Markdown-formatted documents should have this URL set to the address that fetches the raw Markdown content (i.e. under `https://raw.githubusercontent.com`) so that the application can fetch the document to generate context and thumbnails.

`doi`: The "DOI" if the document has been assigned one (e.g. `doi:10.6028/NIST.SP.800-37r1`).

`format`: If the document is not in Document Cloud, the document's format. Can be `markdown`.

`terms`: An array of one or more terms found in the document (see below).

### role

A YAML file may describe a role. Roles have the following fields:

`id`: An identifier for this role unique across all resources within the GovReady Compliance Knowledge Base.

`type`: Always `role`.

`title`: The display title of the role.

`description`: Description text for the role.

`source`: Display text for where this role is defined. (In the future we'll turn this into an identifier of some sort of resource.)

`inherently-governmental`: `yes` or `no` (TODO: Make this a YAML boolean.)

`responsibilities`: A dictionary...

`terms`: An array of one or more terms associated with the role (see below).

### term

A term is a phrase that appears in a document. It has the following attributes:

`text`: The text *exactly* as it appears in the document. If the term appears slightly differently at different locations in the document, a separate term entry must be used. This text is also used as an identifier to refer to this term in term references (see below) both in the same document and in other documents. Therefore if the term `text` is ever changed, it must also be changed in *all* other places it occurs in a term reference in this and any other documents that refer to this term.

`page`: The primary page on which it appears in the document (e.g. where it is defined, if applicable).

`purpose`: This field has the value `definition` if the term is defined within this document (and if  `page` is specified, then on that page).

`defined-by`: A `term-reference` (see below) to where this term is defined.

`same-as`: A `term-reference` (see below) to another term that has the same meaning.

### term-reference

A term-reference is a way of locating a term within a document. A term-reference has the following attributes:

`document`: The identifier (`id`) of the document where the referenced term occurs. If this attribute is missing, then a term is being referenced in the same document that the YAML file is describing --- i.e. to `same-as` two terms that appear in the same document.

`term`: The `text` of the term as it appears in that document. If omitted in a parent term, the term appears with the same words in the referenced document.

Running locally with Docker
---------------------------

To run the Compliance Knowledge Base locally in docker, use the `./startup.sh` script. Note that it will download a large amount of files the first time (working to create an image to speed this up). Once completed, you should be able to visit http://localhost:8000 to see the site.

If you make changes locally that you want to see reflected in the web interface, simply remove the running Docker container and re-run `startup.sh`:
```
docker rm -f compliancekbs
./startup.sh
```

Coding Style Guide
------------------

The official [Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/#indentation) states that spaces, with 4 spaces per level, are the preferred indentation method. Python3 will generate an error if mixed use of tabs and spaces. The Python files here all follow the Python Style Guide and use 4 spaces for indentation.
