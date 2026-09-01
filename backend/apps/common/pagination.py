"""Pagination. One envelope, application-wide.

Set as `DEFAULT_PAGINATION_CLASS`, so every list endpoint paginates unless it
opts out with a comment saying why.
"""
from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """`?page=2&page_size=50`."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class LargeTablePagination(CursorPagination):
    """Keyset pagination for tables where deep offsets get expensive."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = "-created_at"
