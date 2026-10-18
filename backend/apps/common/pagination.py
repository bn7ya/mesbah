from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class LargeTablePagination(CursorPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = "-created_at"
