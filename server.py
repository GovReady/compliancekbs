import sys, os, os.path, glob, re, cgi, datetime, json
import urllib.request
import sqlite3

import rtyaml, CommonMark

from flask import Flask, request, render_template, jsonify

app = Flask(__name__)
app.config.from_object(__name__)
def get_access_log(): return sqlite3.connect('access_log.db')

# Map all resource IDs to the data about them.
all_resources = { }
for fn in glob.glob("resources/*/*.yaml"):
	with open(fn) as f:
		res = rtyaml.load(f)
		all_resources[res['id']] = res

def create_db_tables(access_log):
	# Create database tables on first run..
	c = access_log.cursor()
	for table_name, table_def in [
		("query_log", "query_time datetime, query text, documents_matched text")
	]:
		try:
			c.execute("CREATE TABLE %s (%s)" % (table_name, table_def))
		except sqlite3.OperationalError as e:
			if ("table %s already exists" % table_name) not in str(e):
				raise e
	access_log.commit()

@app.route('/')
def show_demo_page():
    return render_template('api-demo.html')

@app.route('/api/search', methods=['POST'])
def search_documents():
	# q is the search query
	q = request.form['q']

	# run the search query over searchable terms in the YAML files
	# for our documents
	docs = []
	for doc in iter_docs():
		# see if this document matches the query
		context = doc_matches_query(q, doc)
		if context:
			# ...and if so, return it, the match context, and a thumbnail
			# url back to the client
			docs.append({
				"document": doc,
				"context": context,
				"link": doc.get("url") or get_page_url(doc, 1), # if url not specified on document, get from DocumentCloud id
				"thumbnail": get_thumbnail_url(doc, 1, True),
			})

	# log this query
	cur = get_access_log().cursor()
	cur.execute("INSERT INTO query_log values (?, ?, ?)", (
		datetime.datetime.utcnow(),
		q,
		json.dumps([result["document"]["id"] for result in docs]),
	))
	cur.connection.commit()

	# return JSON of all search results
	return jsonify(
		results=docs
	)

def iter_docs():
	# iterate through all of the resources that represent documents
	for res in all_resources.values():
		if res["type"] in ("authoritative-document", "policy-document"):
			yield res

# search

def doc_matches_query(query, doc):
	# Does the query match the title? Return each context in which the
	# query matches the document.

	context = []

	for field in ('title',):
		for ctx in field_matches_query(query, doc.get(field, '')):
			context.append({
				"where": field,
				"text": ctx,
			})

	# does the query match any terms?
	for term in doc.get('terms', []):
		contexts = []

		# does the query match the term as it appears here, or as it appears in a
		# referenced document?
		for path in term_matches_query_recursively(query, doc, term):
			context.append({
				"where": "term",
				"text": format_query_context_path(path),
				"term": term,
				"thumbnail": get_thumbnail_url(doc, term['page'], True) if 'page' in term else None,
				"link": get_page_url(doc, term['page']) if 'page' in term else None,
			})

	# no match (if context is empty, return False)
	return context or False

def field_matches_query(query, value):
	# This is a poor man's implementation of a search server.
	#
	# Make a simple regex out of the query and return a generator over
	# HTML-formatted context strings showing the matched query text

	r = "".join( [(re.escape(c) if re.match(r"[a-zA-Z0-9]", c) else ".?" ) for c in query] )
	for m in re.finditer("(?:^|\W)" + r, value, re.I):
		start, end = m.span()
		yield cgi.escape(value[max(start-50, 0):start]) + "<b>" + cgi.escape(value[start:end]) + "</b>" + cgi.escape(value[end:end+175])

def term_matches_query_recursively(query, document, term, relation_to=None, seen=set()):
	# Does it match the term specified here?
	for ctx in field_matches_query(query, term['term']):
		# It matched, and we have context within the string of the term itself. But if
		# the term says what page it is on, and if we can get the text of that page,
		# then replace the context with context from that page around *that term*
		# (i.e. look for the term in the page, not the original query in the page).
		page_text = get_page_text(document, term.get('page'))
		if page_text:
			for ctx1 in field_matches_query(term["term"], page_text):
				ctx = ctx1
				break

		yield [(ctx, document, relation_to)]
		return # only match once per term

	# Look recursively at any referenced terms if it didn't match exactly here.
	for relation in ('defined-by', 'same-as'):
		if not relation in term: continue

		# How to describe this relation?

		if relation == "defined-by":
			relation_descr = "is defined by"
		else:
			relation_descr = "has same meaning as"

		# Look up the document that the term is referenced in. The `document`
		# field specifies a document ID, or, if omitted, the current document
		# is used.

		if 'document' in term[relation]:
			# prevent infinite loops
			if term[relation]['document'] in seen:
				raise ValueError("cycle in term references")
			refdoc = all_resources[term[relation]['document']]
		else:
			refdoc = document

		# Get the text of the term as it appears in the referenced document.
		# The `term` field specifies the text of the term as it appears in
		# the referenced document. If `term` is omitted, the term has the
		# same text in the referenced document as in the current document.

		if 'term' in term[relation]:
			refterm = term[relation]['term']
		else:
			refterm = term['term']

		# Find the term information in the referenced document.

		ref = next(filter(lambda t : t['term'] == refterm, refdoc['terms']))

		# See if that term matches this query.

		for ctx in term_matches_query_recursively(query, refdoc, ref, relation_to=relation_descr, seen=seen | set([refdoc['id']])):
			yield [(cgi.escape(term["term"]), document, relation_to)] + ctx

def format_query_context_path(path):
	ret = path.pop(0)[0]
	first = True
	if len(path) > 0:
		ret += " <span class=\"from-cited-document\">"
		while len(path) > 0:
			if first:
				ret += "term " # as in, "term is defined by..."
				first = False
			else:
				ret += ", which "
			context, document, relation_descr = path.pop(0)
			ret += cgi.escape(relation_descr) + " “" + context + "” in " + cgi.escape(document.get("short-title", document["id"]))
		ret += "</span>"
	return ret

def get_documentcloud_document_id(doc):
	m = re.match(r"https://www.documentcloud.org/documents/(\d+)-([^\.]+)\.html$", doc.get("url", ""))
	if m:
		return m.group(1), m.group(2)
	return None

def query_documentcloud_api(documentcloud_id):
	# query DocumentCloud API
	return json.loads(urllib.request.urlopen("https://www.documentcloud.org/api/documents/%s-%s.json" % documentcloud_id).read().decode("utf8"))

def get_thumbnail_url(doc, pagenumber, small):
	# If the document is on DocumentCloud, get the URL to DocumentCloud's thumbnail image.
	documentcloud_id = get_documentcloud_document_id(doc)
	if documentcloud_id:
		# We can use the DocumentCloud API to get the URL to a thumbnail, but in the
		# interests of speed, construct the URL ourselves.
		#return query_documentcloud_api(documentcloud_id)["document"]["resources"]["page"]["image"].format(
		#	page=pagenumber,
		#	size="small" if small else "normal",
		#)
		return "https://assets.documentcloud.org/documents/%s/pages/%s-p%d-%s.gif" % (
			documentcloud_id[0], documentcloud_id[1], pagenumber, "small" if small else "normal")

	# If it's a Markdown document, download it, convert it to HTML, then render it to
	# an image, and return that image as a data: URL.
	elif doc.get("format") == "markdown" and os.path.exists("/usr/bin/wkhtmltoimage"):
		md = get_page_text(doc, pagenumber)
		if md:
			import subprocess, base64
			return "data:image/jpeg;base64," + base64.b64encode(
				subprocess.check_output(["/usr/bin/wkhtmltoimage", "--no-images", "--disable-javascript", "--disable-local-file-access", "--width", "300", "--height", "412", "-", "-"],
					input=CommonMark.commonmark(md).encode("utf8"))).decode("ascii")
	return None

def get_page_url(doc, pagenumber):
	# If the document has a DocumentCloud ID, then generate the URL to the thumbnail for
	# its first page.
	documentcloud_id = get_documentcloud_document_id(doc)
	if documentcloud_id:
		return "https://assets.documentcloud.org/documents/%s/%s.pdf#page=%d" % (
			documentcloud_id[0], documentcloud_id[1], pagenumber)
	return None

def get_page_text(doc, pagenumber):
	# Returns the full text of a page.
	documentcloud_id = get_documentcloud_document_id(doc)
	if documentcloud_id and pagenumber is not None:
		# Get the text of the page from DocumentCloud.

		# We can use the DocumentCloud API to get the URL to page text, but in the
		# interests of speed, construct the URL ourselves.
		#url = query_documentcloud_api(documentcloud_id)["document"]["resources"]["page"]["text"].format(
		#	page=pagenumber,
		#)
		url = "https://www.documentcloud.org/documents/%s/pages/%s-p%d.txt" % (
			documentcloud_id[0], documentcloud_id[1], pagenumber)
		return urllib.request.urlopen(url).read().decode("utf8") # TODO: What encoding? Probably use requests library or something that handles that.

	elif doc.get("format") == "markdown" and doc.get("authoritative-url"):
		# Download the document to get its contents. There is only one page
		# in a Markdown document.
		return urllib.request.urlopen(doc.get("authoritative-url")).read().decode("utf8")

	return None

# main entry point

if __name__ == '__main__':
	create_db_tables(get_access_log())
	app.debug = True
	app.run(port=int(os.environ.get("PORT", "8000")))
