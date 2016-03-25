import sys, os, os.path, glob, re, cgi

import rtyaml

from flask import Flask, request, render_template, jsonify

app = Flask(__name__)
app.config.from_object(__name__)

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

	# return JSON of all search results
	return jsonify(
		results=docs
	)

def iter_docs():
	# iterate through all of the YAML files on disk
	for fn in glob.glob("resources/documents/*.yaml"):
		with open(fn) as f:
			yield rtyaml.load(f)

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
		for ctx in field_matches_query(query, term['term']):
			context.append({
				"where": "term",
				"text": ctx,
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
	for m in re.finditer(r, value, re.I):
		start, end = m.span()
		yield cgi.escape(value[max(start-50, 0):start]) + "<b>" + cgi.escape(value[start:end]) + "</b>" + cgi.escape(value[end:end+50])

def get_thumbnail_url(doc, pagenumber, small):
	# If the document has a DocumentCloud ID, then generate the URL to the thumbnail for
	# its first page.
	m = re.match("(\d+)-(.+)", doc.get("document-cloud-id", ""))
	if m:
		return "https://assets.documentcloud.org/documents/%s/pages/%s-p%d-%s.gif" % (
			m.group(1), m.group(2), pagenumber, "small" if small else "normal")
	return None

def get_page_url(doc, pagenumber):
	# If the document has a DocumentCloud ID, then generate the URL to the thumbnail for
	# its first page.
	m = re.match("(\d+)-(.+)", doc.get("document-cloud-id", ""))
	if m:
		return "https://assets.documentcloud.org/documents/%s/%s.pdf#page=%d" % (
			m.group(1), m.group(2), pagenumber)
	return None

# main entry point

if __name__ == '__main__':
    app.debug = True
    app.run(port=8000)
