"""Course discovery endpoint with deterministic title ordering."""

import logging
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from eventtracking import tracker as track
from search import views as search_views
from search.api import course_discovery_aggregations
from search.dataclasses import SortField
from search.filter_generator import SearchFilterGenerator
from search.search_engine_base import SearchEngine
from search.utils import DateRange

log = logging.getLogger(__name__)


def _enable_title_sorting(searcher):
    """Make the title field sortable when the configured engine is Meilisearch."""
    if searcher.__class__.__module__ != "search.meilisearch":
        return

    # Meilisearch requires sortable fields to be registered before they can be used
    # in a search. The adapter applies this list when it first opens the index.
    from search.meilisearch import (  # pylint: disable=import-outside-toplevel
        INDEX_SORTABLES,
        get_meilisearch_client,
        wait_for_task_to_succeed,
    )

    sortable_fields = INDEX_SORTABLES.setdefault(searcher.index_name, [])
    if "content.display_name" not in sortable_fields:
        sortable_fields.append("content.display_name")

    # The search adapter submits this update asynchronously when it opens the
    # index. Wait for the title field to be available before issuing the query,
    # otherwise the first request after a restart can fail with a 400 response.
    index = searcher.meilisearch_index
    if "content.display_name" not in index.get_sortable_attributes():
        task = index.update_sortable_attributes(sortable_fields)
        wait_for_task_to_succeed(get_meilisearch_client(), task)


def _search_courses(search_term, size, from_, field_dictionary):
    """Search one page of courses, ordered by the indexed course title."""
    search_fields, _, exclude_dictionary = SearchFilterGenerator.generate_field_filters()
    use_field_dictionary = {
        field: search_fields[field]
        for field in search_fields
        if field == "org"
    }
    use_field_dictionary.update(field_dictionary or {})

    if not getattr(settings, "SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING", False):
        use_field_dictionary["enrollment_start"] = DateRange(None, datetime.utcnow())

    searcher = SearchEngine.get_search_engine(
        getattr(settings, "COURSEWARE_INFO_INDEX_NAME", "course_info")
    )
    if not searcher:
        raise RuntimeError("No search engine specified in settings.SEARCH_ENGINE")

    _enable_title_sorting(searcher)
    return searcher.search(
        query_string=search_term,
        size=size,
        from_=from_,
        field_dictionary=use_field_dictionary,
        filter_dictionary={"enrollment_end": DateRange(datetime.utcnow(), None)},
        exclude_dictionary=exclude_dictionary,
        aggregation_terms=course_discovery_aggregations(),
        sort_by=[SortField(name="content.display_name")],
        is_multivalue=False,
    )


@require_POST
def course_discovery(request):
    """Return one paginated page of discovery results in title order."""
    results = {"error": _("Nothing to search")}
    status_code = 500
    search_term = request.POST.get("search_string", None)
    try:
        size, from_, page = search_views._process_pagination_values(request)  # pylint: disable=protected-access
        field_dictionary = search_views._process_field_values(  # pylint: disable=protected-access
            request,
            is_multivalue=False,
        )

        track.emit(
            "edx.course_discovery.search.initiated",
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
            },
        )

        # Keep accepting the legacy start-date parameter for API compatibility,
        # but do not let it override the title ordering used by ATS.
        results = _search_courses(search_term, size, from_, field_dictionary)

        track.emit(
            "edx.course_discovery.search.results_displayed",
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
                "results_count": results["total"],
            },
        )
        status_code = 200

    except ValueError as invalid_error:
        results = {"error": str(invalid_error)}
        log.debug(str(invalid_error))

    except Exception as error:  # pylint: disable=broad-exception-caught
        results = {
            "error": _(
                'An error occurred when searching for "{search_string}"'
            ).format(search_string=search_term)
        }
        log.exception(
            "Course discovery exception when searching for %s for user %s: %r",
            search_term,
            request.user.id,
            error,
        )

    return JsonResponse(results, status=status_code)
