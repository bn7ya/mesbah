from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.common.pagination import DefaultPagination
from apps.datasets.models import Dataset
from apps.datasets.serializers import (
    DatasetChangesSerializer,
    DatasetSerializer,
    ImportSerializer,
    RowSerializer,
    UploadSerializer,
)
from apps.datasets.services import DatasetService
from apps.members.permissions import IsTrainer, ViewersReadTrainersWrite


class LibraryView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="datasets_library",
        summary="The dataset library",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(DatasetSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: DatasetService = DatasetService(request.user)

        def render(rows: Iterable[Dataset]) -> list[Any]:
            return [DatasetSerializer(service.describe(row)).data for row in rows]

        return paginate(request, self, service.library(), render)

    @extend_schema(
        operation_id="datasets_import",
        summary="Import a split of a HuggingFace dataset",
        description="Without a mapping, the layout detected from the first rows is used.",
        request=ImportSerializer,
        responses={202: DatasetSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: ImportSerializer = ImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        given: dict[str, Any] = payload.validated_data
        started: dict[str, Any] = DatasetService(request.user).start_import(
            given["repo_id"],
            given["config"],
            given["split"],
            given["row_limit"],
            given.get("mapping"),
        )
        return Response(DatasetSerializer(started).data, status=status.HTTP_202_ACCEPTED)


class UploadView(APIView):
    permission_classes = [IsTrainer]
    parser_classes = [MultiPartParser]

    @extend_schema(
        operation_id="datasets_upload",
        summary="Add a dataset from a .jsonl, .json or .csv file",
        description=(
            "Up to 200 MB. A file under 5 MB is read before the response (201); a larger one is "
            "read in the background (202)."
        ),
        request={"multipart/form-data": UploadSerializer},
        responses={201: DatasetSerializer, 202: DatasetSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: UploadSerializer = UploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        added: dict[str, Any] = DatasetService(request.user).upload(
            payload.validated_data["file"], payload.validated_data["name"]
        )
        ready: bool = added["status"] == Dataset.Status.READY
        code: int = status.HTTP_201_CREATED if ready else status.HTTP_202_ACCEPTED
        return Response(DatasetSerializer(added).data, status=code)


class DatasetView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="datasets_detail",
        summary="One dataset in the library",
        responses={200: DatasetSerializer},
    )
    def get(self, request: Request, dataset_id: str) -> Response:
        service: DatasetService = DatasetService(request.user)
        return Response(DatasetSerializer(service.describe(service.find(dataset_id))).data)

    @extend_schema(
        operation_id="datasets_update",
        summary="Rename a dataset or change its description",
        request=DatasetChangesSerializer,
        responses={200: DatasetSerializer},
    )
    def patch(self, request: Request, dataset_id: str) -> Response:
        payload: DatasetChangesSerializer = DatasetChangesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated: dict[str, Any] = DatasetService(request.user).update(
            dataset_id, payload.validated_data
        )
        return Response(DatasetSerializer(updated).data)

    @extend_schema(
        operation_id="datasets_remove",
        summary="Remove a dataset and its file",
        request=None,
        responses={204: None},
    )
    def delete(self, request: Request, dataset_id: str) -> Response:
        DatasetService(request.user).remove(dataset_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RowsView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="datasets_rows",
        summary="A page of a dataset's rows, as conversations",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(RowSerializer)},
    )
    def get(self, request: Request, dataset_id: str) -> Response:
        rows: Sequence[dict[str, object]] = DatasetService(request.user).rows(dataset_id)
        paginator: DefaultPagination = DefaultPagination()
        # DRF pages any sliceable sequence; its stub only names a QuerySet.
        page: list[Any] = paginator.paginate_queryset(rows, request, view=self) or []  # type: ignore[arg-type]
        return paginator.get_paginated_response([RowSerializer(row).data for row in page])


class CancelImportView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        operation_id="datasets_cancel",
        summary="Stop an import",
        request=None,
        responses={200: DatasetSerializer},
    )
    def post(self, request: Request, dataset_id: str) -> Response:
        return Response(DatasetSerializer(DatasetService(request.user).cancel(dataset_id)).data)


class RetryImportView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        operation_id="datasets_retry",
        summary="Import a failed or stopped dataset again",
        request=None,
        responses={202: DatasetSerializer},
    )
    def post(self, request: Request, dataset_id: str) -> Response:
        retried: dict[str, Any] = DatasetService(request.user).retry(dataset_id)
        return Response(DatasetSerializer(retried).data, status=status.HTTP_202_ACCEPTED)
