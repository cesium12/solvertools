from solvertools.wordlist import WORDS
from solvertools.normalize import slugify, sanitize
from solvertools.util import data_path
from wordfreq import tokenize
from whoosh.index import open_dir
from whoosh import qparser
from operator import itemgetter
from .conceptnet_numberbatch import load_numberbatch, get_vector, similar_to_term
import re

INDEX = None
QUERY_PARSER = None
NUMBERBATCH = None


def simple_parser(fieldname, schema, group, **kwargs):
    """
    Returns a QueryParser configured to support only +, -, and phrase
    syntax.

    Modified from Whoosh's SimpleParser to accept a custom 'group'
    argument.
    """

    pins = [qparser.plugins.WhitespacePlugin,
            qparser.plugins.PlusMinusPlugin,
            qparser.plugins.PhrasePlugin]
    orgroup = qparser.syntax.OrGroup
    return qparser.QueryParser(
        fieldname, schema, plugins=pins, group=orgroup,
        **kwargs
    )


def query_expand(numberbatch, words):
    weighted_words = []
    for word in words:
        similar = similar_to_term(numberbatch, word, limit=25)
        weighted_words.append((word, 1.))
        for word, sim in similar.items():
            weighted_words.append((sanitize(word), sim))
    query_parts = [
        '(%s)^%3.3f' % (word, weight)
        for (word, weight) in weighted_words
    ]
    return ' '.join(query_parts), weighted_words


def search(pattern=None, clue=None, length=None, count=20):
    """
    Find words and phrases that match various criteria: a regex pattern,
    a clue phrase, and/or a length.

    >>> search('.a.b.c..')[0][1]
    'BARBECUE'
    >>> search('.a....e.', clue='US President')[0][1]
    'VAN BUREN'
    >>> search(clue='lincoln assassin', length=15)[0][1]
    'JOHN WILKES BOOTH'
    """
    global INDEX, QUERY_PARSER, NUMBERBATCH
    if clue is None:
        if pattern is None:
            return []
        else:
            return WORDS.search(pattern, count=count, use_cromulence=True)

    if pattern is not None:
        pattern = pattern.lstrip('^').rstrip('$').lower()
        pattern = re.compile('^' + pattern + '$')

    if INDEX is None:
        INDEX = open_dir(data_path('search'))
        QUERY_PARSER = simple_parser(
            fieldname="definition", schema=INDEX.schema,
            group=qparser.OrGroup.factory(0.9)
        )
        QUERY_PARSER.add_plugin(qparser.GroupPlugin())
        QUERY_PARSER.add_plugin(qparser.BoostPlugin())

    if NUMBERBATCH is None:
        NUMBERBATCH = load_numberbatch()

    matches = {}
    with INDEX.searcher() as searcher:
        clue_parts = tokenize(clue, 'en')
        expanded, similar = query_expand(NUMBERBATCH, clue_parts)
        new_clue = '%s, %s' % (sanitize(clue), expanded)
        results = searcher.search(QUERY_PARSER.parse(new_clue), limit=None)
        for word, weight in similar:
            slug = slugify(word)
            if length is None or length == len(slug):
                if pattern is None or pattern.match(slug):
                    matches[word.upper()] = weight * 1000
        for i, result in enumerate(results):
            text = result['text']
            slug = slugify(text)
            if length is None or length == len(slug):
                if pattern is None or pattern.match(slug):
                    score = results.score(i)
                    if text in matches:
                        matches[text] += score
                    else:
                        matches[text] = score
                    if len(matches) >= count:
                        break
        return sorted(matches.items(), key=itemgetter(1), reverse=True)
