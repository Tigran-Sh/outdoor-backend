from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Project-wide default pagination.

    Clients may override the page size with ``?page_size=`` up to a
    sensible maximum.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
