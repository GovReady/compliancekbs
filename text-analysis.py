# Experimental text analysis routines.

import re, math, sys, os.path
from collections import defaultdict

import rtyaml

from nltk.tokenize import sent_tokenize

from server import get_document_text, all_resources

# Globals

max_ngram_size = 3

# Functions

def build_corpus_model():
    # Build the corpus of n-grams in all document text.

    corpus_token_counts = defaultdict(lambda : defaultdict(lambda : 0))

    for res in all_resources.values():
        # Only process documents.
        if res["type"] not in ("authoritative-document", "policy-document"):
            continue

        # Get the full document text, if possible.
        text = get_document_text(res, None)
        if not text:
            continue

        # Draw out n-grams and build up token counts.
        for n in range(1, max_ngram_size+1):
            for boost, ngram in extract_ngrams(n, text):
                corpus_token_counts[n][ngram] += boost

    # Divide the counts by the total number of tokens (really ngrams for each n)
    # so we have relative frequencies.
    normalize_ngrams(corpus_token_counts)

    return corpus_token_counts

def compute_top_terms(res, corpus_token_counts, text):
    # Get the n-gram counts in this document.
    doc_token_counts = defaultdict(lambda : defaultdict(lambda : 0))
    for n in range(1, max_ngram_size+1):
        for boost, ngram in extract_ngrams(n, text):
            doc_token_counts[n][ngram] += boost

    # Divide the counts by the total number of tokens (really ngrams for each n)
    # so we have relative frequencies.
    normalize_ngrams(doc_token_counts)

    # Compute the TF-IDF of each n-gram.
    scores = { }
    for n in range(1, max_ngram_size+1):
        for ngram, doc_count in sorted(doc_token_counts[n].items(), key=lambda kv : -kv[1]):
            tf = get_log_frequency(ngram, doc_token_counts)

            # Because the document is much smaller than the corpus,
            # infrequent words in the document can appear to have
            # a much higher relative frequency in the document than
            # in the corpus. For words whose log frequency approaches
            # one occurrence, scale down their log frequency to be
            # as if it were one occurrence in the entire corpus.
            l1 = math.log(doc_token_counts["_ONE"][len(ngram)])
            l2 = math.log(corpus_token_counts["_ONE"][len(ngram)])
            qmax = 2.25
            q = tf - l1
            if q < qmax:
                # The closer the frequency is to one occurrence in
                # the document the more it is dragged to the relative
                # frequency of one ocurrence in the whole corpus.
                if q < 0 or l1 < l2: raise ValueError()
                tf = (l1+qmax)*(q/qmax) + l2*(1-(q/qmax))

            df = get_adjusted_ngram_log_freq(ngram, corpus_token_counts)
            tf_itf = tf - df # they're in log space, so we subtract

            scores[ngram] = tf_itf

    # Sort by TF-ITF (descending), and then for the sake of producing
    # stable output across runs, sort then by the ngram text.
    return sorted(scores.items(), key = lambda kv : (-kv[1], str(kv[0])))

def extract_ngrams(n, text):
    # Extract n-grams from document text.
    #
    # Because our corpus has a lot of headings and paragraphs,
    # first split on sentences using the NLTK sentence tokenizer
    # so that the n-grams don't pick up phrases that cross
    # heading/sentence/paragraph boundaries.
    #
    # Just just divide on word-ish characters. Since "18F" is
    # a word, let's not make any assumptions about what a word
    # looks like, except that it does not have spaces.
    for sentence in sent_tokenize(text):
        tokens = re.findall(r"\w+", sentence)
        for i in range(len(tokens)-n+1):
            yield (
                # Count tokens that occur in short sentences
                # extra times.
                4 if len(sentence) <= 8 else 1,

                # Extract the n-gram.
                tuple(tokens[i:i+n])
                )

def normalize_ngrams(ngram_counts, smooth_down=False):
    ngram_counts["_ONE"] = {}
    for n in range(1, max_ngram_size+1):
        total = sum(ngram_counts[n].values())
        for k in ngram_counts[n]:
            ngram_counts[n][k] /= total
        ngram_counts["_ONE"][n] = 1/total

def get_log_frequency(ngram, corpus, can_casefold=False):
    # Estimate the log-frequency of the ngram in the corpus.

    # Assume an n-gram occurs at least once, so we don't have
    # to worry about taking the log of zero. If it doesn't occur,
    # return the relative frequency of one occurrence, we was
    # computed earlier.
    if ngram not in corpus[len(ngram)]:
        return math.log(corpus["_ONE"][len(ngram)])

    # Get the relative frequnecy.
    f = math.log(corpus[len(ngram)][ngram])

    # If the n-gram is more frequent when all of the words are
    # lowercased, then use that frequency. i.e. Don't let ngrams
    # become important just because they are at the start of
    # a sentence.
    if can_casefold:
        normalized_ngram = tuple(w.lower() for w in ngram)
        if ngram != normalized_ngram:
            f = max(f, get_log_frequency(normalized_ngram, corpus))

    return f

def get_estimated_log_frequency(ngram, corpus):
    # Compute an estimate of the frequency of the n-gram (for n > 1)
    # that is the product of the expected frequencies of the sub-ngrams
    # that make up the n-gram by dividing it into (n-1 grams and n-2
    # grams and so on, and taking the max estimated frequency across
    # those divisions).
    return max(
        sum(
            # sum the products of the m=n-1 m-grams that
            # make up the n-gram (possibly with a smaller
            # n-gram at the end)
            get_log_frequency(ngram[i:i+n], corpus, can_casefold=True)
            for i in range(0, len(ngram), n)
        )
        for n in range(1, len(ngram))

    # Boost it a little so that we always estimate that a term is
    # a little more frequent than we have data for.
    ) + 1*len(ngram)

def get_adjusted_ngram_log_freq(ngram, corpus):
    # Return the actual log relative frequency of the ngram, or its
    # estimated frequency if the estimated frequency is actually
    # higher (which might be because of sparse data).
    ret = get_log_frequency(ngram, corpus, can_casefold=True)
    if len(ngram) > 1:
        ret = max(ret, get_estimated_log_frequency(ngram, corpus))
    return ret

# Main Entry Point

if __name__ == "__main__":
    corpus_token_counts = build_corpus_model()

    if len(sys.argv) == 1:
        # Perform TF-ITF on each document and print the n-grams
        # that have the highest score per document.

        for res in sorted(all_resources):
            # Only process documents.
            res = all_resources[res]
            if res["type"] not in ("authoritative-document", "policy-document"):
                continue

            print(res["id"])
            print("-" * len(res["id"]))

            # Get the full document text, if possible.
            text = get_document_text(res, None)
            if not text:
                continue

            # Compute terms.
            terms = compute_top_terms(res, corpus_token_counts, text)

            for ngram, score in terms[0:15]:
                #print(score, ngram)
                print(" ".join(ngram))

            print()

    else:
        # The command-line argument is a document ID to add terms
        # into.

        res = all_resources[sys.argv[1]]

        # Get the full document text.
        text = get_document_text(res, None)
        if not text:
            # Use pdftotext as a fallback.
            import urllib.request, subprocess
            text = subprocess.check_output(["pdftotext", "-", "-"],
                input=urllib.request.urlopen(res["authoritative-url"]).read())\
                .decode("utf8")

            if not text:
                print("Document %s has no fetchable text." % res['id'])
                sys.exit(1)

        # Compute terms.
        terms = compute_top_terms(res, corpus_token_counts, text)
        if len(terms) == 0:
            print("Didn't find any terms.")
            sys.exit(1)

        # Add terms.
        res.setdefault("terms", [])
        for ngram, score in terms[0:30]:
            # Convert tuple back to text.
            term = " ".join(ngram)

            # Already has this term?
            if len([t for t in res["terms"] if t["text"] == term]) > 0:
                print("Already has term", term)
                continue

            # Add.
            print("Adding term", term)
            res["terms"].append({
                "text": term
            })

        # Save. Guess its file name -- hopefully based on its ID.
        fn = os.path.join("resources", "documents", res["id"] + ".yaml")
        with open(fn, "w") as f:
            f.write(rtyaml.dump(res))

