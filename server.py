# HTTP API + Demo Page Server
#############################

# This is a Flask HTTP daemon which serves the GovReady Compliance
# Knowledge Base API, plus some static resources for a demo page.

################################################################################

import sys, os, os.path, glob, re, html, datetime, json, collections, time
import urllib.request, urllib.error
import sqlite3

import rtyaml, CommonMark

from flask import Flask, request, render_template, jsonify

################################################################################

# Globals

app = Flask(__name__)
app.config.from_object(__name__)
app.config['DATABASE_FILENAME'] = 'access_log.db'
app.debug = True

def get_access_log():
    db = sqlite3.connect(app.config['DATABASE_FILENAME'])
    db.row_factory = sqlite3.Row
    return db

# Pre-load all of the resource files, because there aren't so many of
# them in this prototype, and map all resource IDs to the data about them,
# so that we can find them quickly.
all_resources = { }
for fn in glob.glob("resources/*/*.yaml"):
    with open(fn) as f:
        res = rtyaml.load(f)
        all_resources[res['id']] = res

################################################################################

# Initialization routines.

def create_db_tables(access_log):
    # We store a query log in an Sqlite database. Initialize the
    # log table if it's not present already.
    c = access_log.cursor()
    for table_name, table_def in [
        ("meta", "key TEXT, value TEXT"),
        ("query_log", "query_time DATETIME, remote_ip TEXT, query TEXT, documents_matched TEXT, execution_duration INTEGER")
    ]:
        try:
            # Execute CREATE TABLE command.
            c.execute("CREATE TABLE %s (%s)" % (table_name, table_def))

            # Set initial db schema.
            print("Created db table", table_name)
            if table_name == "meta":
                c.execute("INSERT INTO meta VALUES('dbschemaver', ?)", str(1))
        except sqlite3.OperationalError as e:
            # If we get an error that it already exists, that's perfect
            # --- nothing for us to do. Other errors are errors.
            if ("table %s already exists" % table_name) not in str(e):
                raise e
    access_log.commit()

    # Schema migrations.
    while True:
        schemaver = int((c.execute("SELECT value FROM meta WHERE key = 'dbschemaver'").fetchone() or [0])[0])
        if schemaver == 1:
            print("Adding execution_duration column to query_log table.")
            c.execute("ALTER TABLE query_log ADD execution_duration INTEGER")
        else:
            break
        c.execute("UPDATE meta SET value = ? WHERE key = 'dbschemaver'", str(schemaver+1))

    # Commit db changes.
    access_log.commit()

################################################################################

# Routes - Static Pages

@app.route('/')
def show_demo_page():
    # The / URL shows the HTML demo page.
    return render_template('api-demo.html')

@app.route('/vocabulary')
def show_vocab_page():
    # The /vocabulary URL shows the vocabulary listing page.
    return render_template('vocabulary.html')

@app.route('/roles')
def show_roles_page():
    # The /roles URL shows the roles listing page.
    return render_template('roles.html')

@app.route('/query-stats')
def show_query_stats_page():
    # The /roles URL shows the roles listing page.
    return render_template('query-stats.html')

################################################################################

# Routes - The Search API

@app.route('/api/search', methods=['GET'])
def search_documents():
    # This is the search API. The user passes a single 'q'
    # GET parameter, which is the query.

    # q is the search query; if empty, return immediately
    q = request.args.get("q")
    if not q:
        return jsonify()

    # Log the duration of the query.
    query_start_time = time.time()

    # Run the search query over searchable resources. Return each
    # resource that matches, plus some contextual information
    # about the match, and other metadata.
    results = []
    for resource in iter_searchable_resources():

        # Does this document match the query? If so, context will
        # be an array of contexts that show how the query matched.
        context = doc_matches_query(q, resource)
        if context:
            # If there is any matching context, include the matched
            # resource in the results, plus the context, etc.
            results.append({
                "resource": resource, # exactly the same as the YAML file contents
                "context": context, # an array of contexts
                "thumbnail": get_thumbnail_url(resource, 1, True), # generate a thumbnail URL
            })

    # TODO: Put the results in some sort of order.

    # Log this query in the database.
    query_end_time = time.time()
    cur = get_access_log().cursor()
    cur.execute("INSERT INTO query_log values (?, ?, ?, ?, ?)", (
        datetime.datetime.utcnow(),
        request.remote_addr,
        q,
        " ".join([result["resource"]["id"] for result in results]),
        int(round((query_end_time-query_start_time)*1000)), # convert to integral miliseconds
    ))
    cur.connection.commit()

    # Return a JSON object of all search results.
    return jsonify(
        results=results
    )

def iter_searchable_resources():
    # Returns a generator that iterates through all of the resources that
    # can be searched by the API (documents & roles).
    for res in all_resources.values():
        if res["type"] in ("authoritative-document", "policy-document", "role"):
            yield res

def iter_roles():
    # Returns a generator that iterates through all of the resources that
    # represent roles.
    for res in all_resources.values():
        if res["type"] in ("role",):
            yield res

# Search core routines.

def doc_matches_query(query, resource):
    # Checks if a resource matches a search query.
    #
    # If so, returns an array of contextual info showing how the query matched.
    # If the resource does not match, returns an empty list.

    context = []

    # Perform exact string comparison on resource IDs.
    if resource["id"] in query.split(" "):
        context.append({
            "html": html.escape(resource["id"]),
        })

    # Perform simple text matching on the titles and description of the resource.

    def run_simple_test(value):
        for ctx in field_matches_query(query, value):
            context.append({
                "html": ctx,
            })

    for field in ('title', 'description'):
        run_simple_test(resource.get(field, ''))
    for title in resource.get("alt-titles", []):
        run_simple_test(title)

    # Compare the query to each 'term' that is listed in the resource's terms list.
    # The query may match against the term itself, or any term that it is
    # defined-by or same-as (or recursively so).
    for term in resource.get('terms', []):
        # For each term, get all of the ways the query matches this term. There
        # can be more than one way a term matches a query, especially since we're
        # looking recursively at the network of term relationships. Is showing
        # them all helpful? Maybe not (but then we'd need a way to prioritize).
        term_matches = term_matches_query_recursively(query, resource, term)
        for term_match in term_matches:
            context.append({
                # Render the match as HTML for display.
                "html": format_term_match(term_match),

                # Generate a thumbnail URL for the term if the term has a 'page'
                # and if the resource is a document that has page thumbnails.
                "thumbnail": get_thumbnail_url(resource, term['page'], True) if 'page' in term else None,

                # Generate a URL to the page that the term occurs on, if applicable.
                "link": get_page_url(resource, term['page']) if 'page' in term else None,
            })

    # Return what we found.
    return context

def field_matches_query(query, value):
    # Test if a string value matches the search query.
    #  
    # Returns a generator over HTML snippets showing the context in which
    # the search query matched. If there is no match, the generator simply
    # contains nothing.

    # Make a simple regex out of the query string:
    #  letters and numbers in the query must match example
    #  other characters match against any single character or no character

    r = "".join([
        (        re.escape(c) if re.match(r"[a-zA-Z0-9]", c)
            else ".?" )
        for c in query
    ])

    # The regex matches all word prefixes (i.e. at start of the string
    # or after any non-word character).
    r = "(?:^|\W)" + r

    # Find all occurrences of this regex in the string.

    for m in re.finditer(r, value, re.I):
        # Generate and yield an HTML snippet that shows some context
        # before and after the match, with the match in bold.

        start, end = m.span()

        context_before = value[max(start-50, 0):start]
        matched_text = value[start:end]
        context_after = value[end:end+175]

        yield html.escape(context_before) + "<b>" + html.escape(matched_text) + "</b>" + html.escape(context_after)

def term_matches_query_recursively(query, resource, term, relation_to=None, seen=set()):
    # Tests if a term matches a query.

    # Prevent infinite recursion as we chain across links between terms.
    if (resource["id"], term["text"]) in seen:
        return
    seen = seen | set([(resource['id'], term["text"])])

    # Test if the term itself (its "text") matches the query.

    for ctx in field_matches_query(query, term['text']):
        # It matched, and we have context within the text of the term itself.
        # We could return that context.
        #
        # If the term says what page it is on, and if we can get the text of that page,
        # then replace the context with context from that page around *that term*
        # (i.e. look for the term in the page, not the original query in the page).
        page_text = get_page_text(resource, term.get('page'))
        if page_text:
            for ctx1 in field_matches_query(term["text"], page_text):
                ctx = ctx1
                break

        # Yield the context HTML, plus this resource, and the relation_to from the
        # resource that sent us here (recursively), which let's us reconstruct how
        # we got here.
        yield [(ctx, resource, relation_to)]

        # If the term's text matches, just return the first way it matches
        # and don't bother looking further recursively.
        return

    # Look recursively at any terms this term references.

    for relation in ('defined-by', 'same-as'):
        if not relation in term: continue

        # Look up the document that the referenced term occurs in.

        if 'document' in term[relation]:
            # The 'document' field specifies the ID of a document resource
            # that the referenced term occurs in.
            if term[relation]['document'] in seen: raise ValueError("cycle in term references")
            ref_res = all_resources[term[relation]['document']]
        else:
            # When no 'document' field is specified, the reference is to
            # a term that occurs in the same document.
            ref_res = resource

        # Get the name of the referenced term.

        if 'term' in term[relation]:
            # The `term` field specifies the text of the term as it appears in
            # the referenced document.
            ref_term_text = term[relation]['term']
        else:
            # If `term` is omitted, the term has the same text in the referenced 
            # document as in the current document.
            ref_term_text = term['text']

        # Find the term information in the referenced document. Loop through all
        # of the terms in the referenced document until we find the one that
        # matches the term text of the referenced term.

        for t in ref_res.get('terms', []):
            if t['text'] == ref_term_text:
                ref_term = t
                break
        else:
            # 'break' was not executed
            raise ValueError("Term reference in resource <%s> to \"%s\" in resource <%s> is invalid."
                % (resource["id"], ref_term_text, ref_res['id']) )

        # See if the referenced term matches this query. Pass through
        # each match found in the recursive call.

        for ctx in term_matches_query_recursively(query, ref_res, ref_term, relation_to=relation, seen=seen):
            # Return the context obtained by the recursive call, but prepend
            # information about the original term and the relationship between
            # the original term and the referenced term to make a path, so that
            # we can reconstruct how the document matched through a chain of
            # term relationships.
            yield [(html.escape(term["text"]), resource, relation_to)] + ctx

def format_term_match(path):
    # When a term matches, we get a path from a term in a document that is
    # included in search results, through term relationships, to a term that
    # actually matched the search query, which might be in another document.
    #
    # The data structure is like this:
    #  [
    #    ("term", { resource }, None),
    #    ...
    #    ("term", { resource }, "defined-by"),
    #    ("term", { resource }, "defined-by"),
    #  ]
    # Where each relationship (e.g. "defined-by") indicates the relationship
    # between the tuple entry in which it occurs and the previous tuple entry.
    # The first one is always None because there is no previous entry.
    #
    # The output is something like:
    #
    # X [term is defined by term "Y" in document "Z", which is defined by
    # ....]

    ret, base_document, dummy = path.pop(0)
    
    # When there is more than one entry, then indicate the path as contexual
    # info.
    first = True
    if len(path) > 0:
        ret += " <span class=\"from-cited-document\">"
        while len(path) > 0:
            # Some initial static text.
            if first:
                ret += "term " # as in, "term is defined by..."
                first = False
            else:
                ret += ", which "

            # Get the next item.
            context, document, relation = path.pop(0)

            # How to describe this relation?
            if relation == "defined-by":
                relation_descr = "is defined by"
            else:
                relation_descr = "has same meaning as"

            # More text.
            ret += html.escape(relation_descr + " term “") + context + html.escape("”")

            # Only show "in <xxx document>" starting when an element in
            # the path is not in the same document as the first element's
            # document. i.e. So long as the path remains in the first
            # document, there is no need to be explicit about what document
            # the term appears in.
            if document != base_document:
                ret += " in " + html.escape(document.get("short-title", document["id"]))
                base_document = None # show the document in all future elements

        ret += "</span>"
    return ret

def get_documentcloud_document_id(doc):
    # If the resource's url is a DocumentCloud document URL, return
    # the document's DocumentCloud ID, which is a tuple of a numeric
    # ID and a slug-like string.
    m = re.match(r"https://www.documentcloud.org/documents/(\d+)-([^\.]+)\.html$", doc.get("url", ""))
    if m:
        return m.group(1), m.group(2)
    return None

def query_documentcloud_api(documentcloud_id):
    # Query the DocumentCloud API given a DocumentCloud document ID.
    # Returns the document resource metadata.
    return json.loads(urllib.request.urlopen("https://www.documentcloud.org/api/documents/%s-%s.json" % documentcloud_id).read().decode("utf8"))

def get_thumbnail_url(doc, pagenumber, small):
    # Returns a URL to a thumbnail image for a particular page of the document.
    # 'small' is a boolean.

    # If the document is on DocumentCloud, get the URL to DocumentCloud's thumbnail image.
    documentcloud_id = get_documentcloud_document_id(doc)
    if documentcloud_id:
        # We can use the DocumentCloud API to get the URL to a thumbnail, but in the
        # interests of speed, construct the URL ourselves.
        #return query_documentcloud_api(documentcloud_id)["document"]["resources"]["page"]["image"].format(
        #    page=pagenumber,
        #    size="small" if small else "normal",
        #)
        return "https://assets.documentcloud.org/documents/%s/pages/%s-p%d-%s.gif" % (
            documentcloud_id[0], documentcloud_id[1], pagenumber, "small" if small else "normal")

    # If it's a Markdown document, download it, convert it to HTML, then render it to
    # a PDF, and then to an image, and return that image as a data: URL.
    elif doc.get("format") == "markdown" and os.path.exists("/usr/bin/htmldoc") and os.path.exists("/usr/bin/pdftoppm"):
        # Download the Markdown file.
        md = get_page_text(doc, pagenumber)

        # If we got it...
        if md:
            import subprocess, base64

            # Render the Markdown as HTML.
            html = CommonMark.commonmark(md)

            # Render the HTML as a PDF.
            # TODO: Possible security issue if the Markdown source can generate HTML that
            # causes htmldoc to perform network requests or possibly unsafe operations.
            pdf = subprocess.check_output(["/usr/bin/htmldoc", "--quiet", "--continuous",
                "--size", "4.5x5.8in", # smaller page magnifies the text
                "--top", "0", "--right", "1cm", "--bottom", "1cm", "--left", "1cm", # margins
                "-t", "pdf14", "-"],
                input=html.encode("utf8"))

            # Render the PDF and a PNG.
            png = subprocess.check_output(["/usr/bin/pdftoppm", "-singlefile", "-r", "60", "-png"],
                input=pdf)

            # Return a data: URL so we don't have to store/host the image anywhere,
            # but we can display it directly.
            return "data:image/png;base64," + base64.b64encode(png).decode("ascii")

    # No thumbnail image is available for this resource.
    return None

def get_page_url(doc, pagenumber):
    # If the document has a DocumentCloud ID, then generate the URL to browse
    # the indicated page of the document.
    documentcloud_id = get_documentcloud_document_id(doc)
    if documentcloud_id:
        return "https://www.documentcloud.org/documents/%s-%s.html#document/p%d" % (
            documentcloud_id[0], documentcloud_id[1], pagenumber)
    return None

def get_page_text(doc, pagenumber):
    # Returns the full text of a page of a document.

    # Get the text of the page from DocumentCloud, if the document is on DocumentCloud.
    documentcloud_id = get_documentcloud_document_id(doc)
    if documentcloud_id and pagenumber is not None:
        # We can use the DocumentCloud API to get the URL to page text, but in the
        # interests of speed, construct the URL ourselves.
        #url = query_documentcloud_api(documentcloud_id)["document"]["resources"]["page"]["text"].format(
        #    page=pagenumber,
        #)
        url = "https://www.documentcloud.org/documents/%s/pages/%s-p%d.txt" % (
            documentcloud_id[0], documentcloud_id[1], pagenumber)

        # Download the text at the URL.
        # TODO: What encoding is it coming back as? Probably better to use requests
        # library or something that handles that automatically. Assume UTF-8 now.
        try:
            return urllib.request.urlopen(url).read().decode("utf8")
        except urllib.error.HTTPError as e:
            # Silently ignore errors.
            return None

    # If the document is a Markdown document, fetch the text from the authoritative-url.
    # Return the raw Markdown, which is good enough to be the text of the page.
    # (i.e., We can't render Markdown to plain text.)
    elif doc.get("format") == "markdown" and doc.get("authoritative-url"):
        # Download the document to get its contents. There is only one page
        # in a Markdown document.
        return urllib.request.urlopen(doc.get("authoritative-url")).read().decode("utf8")

    # No text is available.
    return None

# Routes - The List APIs

# Vocabulary listing.

@app.route('/api/vocab', methods=['GET'])
def vocab():
    # Get a list of all of the terms in all of the searchable resources.
    # Since a term can appear in multiple documents (or at least, terms with
    # the same text can), we'll group by term text, and then withini each
    # list all of the resources that the term occured in.
    
    terms = collections.defaultdict(lambda : [])

    # For each term in each resource...
    for doc in iter_searchable_resources():
        for term in doc.get("terms", []):
            # Append the term and document to the list for this term text.
            terms[term["text"]].append({
                "text": term["text"],
                "document": doc["id"],
            })

    # Sort - alphabetically, but ignoring case-ish.
    terms = sorted(terms.values(), key=lambda term : (term[0]["text"].lower(), term[0]["text"]))

    # Return.
    return jsonify(terms=terms)

# Roles listing.

@app.route('/api/roles', methods=['GET'])
def roles():
    # Get a list of all of the roles and just return the YAML data
    # directly.
    roles = sorted(iter_roles(), key=lambda role : (role["title"].lower(), role["title"]))
    return jsonify(roles=roles)

################################################################################

# Query Statistics API

@app.route('/api/querystats', methods=['GET'])
def query_stats():
    # Return a report of statistics on the queries based on the access log.

    # Fetch the recent queries.
    cursor = get_access_log().cursor()
    recent_queries = cursor.execute("SELECT * FROM query_log ORDER BY query_time DESC LIMIT 250").fetchall()

    def top_by_count(seq, N=20):
        counts = { }
        for item in seq:
            counts[item] = counts.get(item, 0) + 1
        return sorted(counts.items(), key = lambda kv : kv[1], reverse=True)[0:N]

    # Find the most frequent query.
    by_query = top_by_count(q["query"] for q in recent_queries)

    # ... and where the query resulted in no matches.
    by_query_no_results = top_by_count(q["query"] for q in recent_queries if q["documents_matched"] == "")

    # Find the most frequently returned document.
    by_doc = top_by_count(
        resource_id for resource_id in
          sum((q["documents_matched"].split(" ") for q in recent_queries), [])
          if resource_id != "" # for queries that match nothing
        )

    return jsonify(
        most_freq_queries=by_query,
        most_freq_queries_no_results=by_query_no_results,
        most_freq_docs=by_doc,
        )


################################################################################

# main entry point

if __name__ == '__main__':
    # Initialization.
    create_db_tables(get_access_log())

    # Run the Flask server, listening on all network interfaces.
    # Use a default port of 8000 unless the PORT environment variable
    # is given.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
