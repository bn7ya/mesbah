from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, cast

from django.db.models import Model, QuerySet
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import DefaultPagination

PAGE_PARAMETERS: list[OpenApiParameter] = [
    OpenApiParameter("page", int, description="Page number, from 1."),
    OpenApiParameter("page_size", int, description="Rows per page, up to 200."),
]


def page_of(item: type[serializers.Serializer[Any]]) -> type[serializers.Serializer[Any]]:
    name: str = item.__name__.removesuffix("Serializer")
    fields: dict[str, serializers.Field[Any, Any, Any, Any]] = {
        "count": serializers.IntegerField(),
        "next": serializers.URLField(allow_null=True),
        "previous": serializers.URLField(allow_null=True),
        "results": item(many=True),
    }
    return cast(
        "type[serializers.Serializer[Any]]",
        type(f"{name}PageSerializer", (serializers.Serializer,), fields),
    )


def paginate[TModel: Model](
    request: Request,
    view: APIView,
    rows: QuerySet[TModel],
    render: Callable[[Iterable[TModel]], list[Any]],
) -> Response:
    paginator: DefaultPagination = DefaultPagination()
    page: list[TModel] = paginator.paginate_queryset(rows, request, view=view) or []
    return paginator.get_paginated_response(render(page))
