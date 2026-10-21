from functools import reduce
from operator import and_

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import connection
from django.db.models import F, TextField, Value
from rest_framework import serializers

from access.policies import can_remark, can_task, selectable_projects
from content.search_config import LANGUAGES, query_groups, search_text, search_vector
from core.api import StrictSerializer
from core.domain import DomainError, current_user
from projects.services import validated
from remarks.models import Remark
from tasks.models import Task


class SearchInput(StrictSerializer):
    q = serializers.CharField(max_length=200)
    page = serializers.IntegerField(min_value=1, default=1)


def normalized_queries(text):
    queries = {}
    with connection.cursor() as cursor:
        for language, words in query_groups(text).items():
            cursor.execute('SELECT plainto_tsquery(%s::regconfig, %s)::text', [language, words])
            value = cursor.fetchone()[0]
            if value:
                # PostgreSQL produced these lexemes. The simple configuration
                # preserves them, avoiding a second language-specific stemming.
                queries[language] = SearchQuery(value, config='simple', search_type='raw')
    return queries


def search_content(actor, params):
    actor = current_user(actor)
    if hasattr(params, 'getlist') and any(len(params.getlist(key)) != 1 for key in params):
        raise DomainError('invalid_input', 'Supply each search parameter once.')
    values = validated(SearchInput, params)
    queries = normalized_queries(values['q'])
    if not queries:
        return {'count': 0, 'next': None, 'results': []}
    query = reduce(and_, queries.values())
    projects = list(selectable_projects(actor))
    task_projects = [p.pk for p in projects if can_task(actor, p)]
    remark_projects = [p.pk for p in projects if can_remark(actor, p)]

    def matches(rows, kind, fields, title, destination):
        vector = search_vector(*fields)
        snippets = {f'snippet_{language}': SearchHeadline(
            search_text(*fields), queries[language], config=language,
            start_sel='[', stop_sel=']', max_words=35, min_words=10, short_word=2,
            max_fragments=2, fragment_delimiter=' … ') if language in queries
            else Value('', output_field=TextField()) for language in LANGUAGES}
        return rows.annotate(document=vector).filter(document=query).annotate(
            kind=Value(kind), label=F(title), destination=F(destination),
            rank=SearchRank(vector, query, normalization=32), **snippets).order_by().values(
                'id', 'kind', 'label', 'destination', 'rank', *(f'snippet_{language}' for language in LANGUAGES))

    tasks = matches(Task.objects.filter(project_id__in=task_projects), 'task', ('title', 'description'), 'title', 'id')
    remarks = matches(Remark.objects.filter(task__project_id__in=remark_projects), 'remark', ('body',), 'task__title', 'task_id')
    rows = tasks.union(remarks, all=True).order_by('-rank', 'kind', 'id')
    count = rows.count()
    start = (values['page'] - 1) * 50
    result = []
    for row in rows[start:start + 50]:
        snippets = list(dict.fromkeys(row[f'snippet_{language}'][:500] for language in LANGUAGES if row[f'snippet_{language}']))
        result.append({'kind': row['kind'], 'id': str(row['id']), 'task': str(row['destination']),
                       'label': row['label'], 'snippets': snippets})
    return {'count': count, 'next': values['page'] + 1 if start + 50 < count else None, 'results': result}
