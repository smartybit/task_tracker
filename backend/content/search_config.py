"""Shared indexing/query language policy. Schema migrations freeze its expressions."""
import re
from functools import reduce
from operator import add

from django.contrib.postgres.search import SearchVector
from django.db.models import F, Func, TextField, Value
from django.db.models.functions import Concat

LANGUAGES = ('english', 'russian')
WORDS = re.compile(r'[^\W_]+', re.UNICODE)
CYRILLIC = re.compile(r'[\u0400-\u052f]')
TOKENS = r'\[(task|remark|image):[0-9a-fA-F-]{36}\]'


def search_text(*fields):
    expressions = []
    for field in fields:
        if expressions:
            expressions.append(Value(' '))
        expressions.append(F(field))
    text = Concat(*expressions, output_field=TextField()) if len(expressions) > 1 else expressions[0]
    return Func(text, Value(TOKENS), Value(' '), Value('g'), function='regexp_replace', output_field=TextField())


def search_vector(*fields):
    return reduce(add, (SearchVector(search_text(*fields), config=language) for language in LANGUAGES))


def query_groups(text):
    groups = {language: [] for language in LANGUAGES}
    for word in WORDS.findall(text):
        groups['russian' if CYRILLIC.search(word) else 'english'].append(word)
    return {language: ' '.join(words) for language, words in groups.items() if words}
