from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message
from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer, IsViewer, ViewersReadTrainersWrite
from apps.training.models import TrainingMetric, TrainingRun
from apps.training.serializers import (
    ExampleSerializer,
    MetricQuerySerializer,
    MetricSerializer,
    NewRunSerializer,
    PlanSerializer,
    ProjectQuerySerializer,
    RunSerializer,
)
from apps.training.services import ExampleService, TrainingService

PROJECT_PARAMETER: OpenApiParameter = OpenApiParameter(
    "project", str, required=True, description="The project's id."
)


def project_of(request: Request) -> str:
    query: ProjectQuerySerializer = ProjectQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return str(query.validated_data["project"])


class RunListView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="training_runs",
        summary="A project's training runs, newest first",
        parameters=[PROJECT_PARAMETER, *PAGE_PARAMETERS],
        responses={200: page_of(RunSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: TrainingService = TrainingService(request.user)

        def render(runs: Iterable[TrainingRun]) -> list[Any]:
            return [RunSerializer(service.describe(run)).data for run in runs]

        return paginate(request, self, service.listing(project_of(request)), render)

    @extend_schema(
        summary="Train a new version",
        description=(
            "Starts from `starts_from` (the active version when left out) and learns from the "
            "project's approved replies. Runs one at a time; a second waits for the first."
        ),
        request=NewRunSerializer,
        responses={202: RunSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: NewRunSerializer = NewRunSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        fields: dict[str, Any] = dict(payload.validated_data)
        fields["project"] = str(fields["project"])
        if fields.get("starts_from") is not None:
            fields["starts_from"] = str(fields["starts_from"])
        service: TrainingService = TrainingService(request.user)
        run: TrainingRun = service.create(**fields)
        return Response(RunSerializer(service.describe(run)).data, status=status.HTTP_202_ACCEPTED)


class PlanView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="training_plan",
        summary="What a new run would start with",
        description="Settings suited to this machine and model, and how many replies are approved.",
        parameters=[PROJECT_PARAMETER],
        responses={200: PlanSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response(
            PlanSerializer(TrainingService(request.user).plan(project_of(request))).data
        )


class ExampleListView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="training_examples",
        summary="The approved replies a run learns from, as conversations",
        parameters=[PROJECT_PARAMETER, *PAGE_PARAMETERS],
        responses={200: page_of(ExampleSerializer)},
    )
    def get(self, request: Request) -> Response:
        project: str = project_of(request)
        TrainingService(request.user).project(project)
        examples: ExampleService = ExampleService()

        def render(replies: Iterable[Message]) -> list[Any]:
            return [ExampleSerializer(examples.describe(reply)).data for reply in replies]

        return paginate(request, self, examples.corrections(project), render)


class RunDetailView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(operation_id="training_run", summary="One run", responses={200: RunSerializer})
    def get(self, request: Request, run_id: str) -> Response:
        service: TrainingService = TrainingService(request.user)
        return Response(RunSerializer(service.describe(service.find(run_id))).data)

    @extend_schema(summary="Remove a finished run", request=None, responses={204: None})
    def delete(self, request: Request, run_id: str) -> Response:
        TrainingService(request.user).remove(run_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CancelRunView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        summary="Stop a run",
        description="A waiting run stops at once; a running one at its next step, saving nothing.",
        request=None,
        responses={200: RunSerializer},
    )
    def post(self, request: Request, run_id: str) -> Response:
        service: TrainingService = TrainingService(request.user)
        return Response(RunSerializer(service.describe(service.cancel(run_id))).data)


class MetricListView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="training_metrics",
        summary="A run's loss and learning rate by step",
        parameters=[
            OpenApiParameter("after_step", int, description="Only steps after this one."),
            *PAGE_PARAMETERS,
        ],
        responses={200: page_of(MetricSerializer)},
    )
    def get(self, request: Request, run_id: str) -> Response:
        query: MetricQuerySerializer = MetricQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows: Any = TrainingService(request.user).metrics_of(
            run_id, query.validated_data["after_step"]
        )

        def render(points: Iterable[TrainingMetric]) -> list[Any]:
            return [
                MetricSerializer(
                    {
                        "step": point.step,
                        "epoch": point.epoch,
                        "loss": point.loss,
                        "learning_rate": point.learning_rate,
                        "grad_norm": point.grad_norm,
                    }
                ).data
                for point in points
            ]

        return paginate(request, self, rows, render)
