# compliancekbs
Compliance Knowledge Base Service for Security Controls Compliance Server

![Screenshot of Compliance Knowledge Base Service](/static/compliancekbs-schreenshot.png?raw=true "Screenshot of Compliance Knowledge Base Service")

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

The columns are the date/time of the query (in UTC), the user's IP address, the user's query, and a space-separated list of document IDs that were returned by the query (in the order in which they were returned).


YAML schema
-----------

### documnet

Each YAML file describes a document. Documents have the following fields:

`id`: An identifier for this document unique within the GovReady Compliance Knowledge Base. This `id` is used within term references (see below) to refer to this document from other documents. Therefore if an `id` is ever changed, it must also be changed in *all* other documents that refer to this document.

`type`: Either `authoritative-document` for a law, regulation, or other similar document (e.g., NIST documents) or `policy-document` for a policy implementation by an agency (e.g., 18F and CMS documents).

`owner`: Display text for who authored the document (e.g. `NIST`, `CMS`, `18F`). (In the future we'll turn this into an identifier of some sort of resource.)

`title`: The display title of the document.

`short-title`: A short form display title of the document.

`url`: The preferred URL where the document can be viewed. This is a link for humans. We recognize URLs that look like `https://www.documentcloud.org/documents/###-____.html` for displaying thumbnails from DocumentCloud.

`authoritative-url`: A link to the authoritative copy of a document, i.e. as published by the document owner. The URL should return a direct download link for a file in the format given in the `format` document property. Markdown-formatted documents should have this URL set to the address that fetches the raw Markdown content (i.e. under `https://raw.githubusercontent.com`) so that the application can fetch the document to generate context and thumbnails.

`doi`: The "DOI" if the document has been assigned one (e.g. `doi:10.6028/NIST.SP.800-37r1`).

`format`: If the document is not in Document Cloud, the document's format. Can be `markdown`.

`terms`: An array of one or more terms found in the document (see below).

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
