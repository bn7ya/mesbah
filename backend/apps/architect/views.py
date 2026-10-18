from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.architect.models import ArchitectureDraft
from apps.architect.serializers import (
    DraftChangeSerializer,
    DraftSerializer,
    EstimateRequestSerializer,
    EstimateSerializer,
    NewDraftSerializer,
    PresetListSerializer,
    TrainDesignSerializer,
    TrainStartedSerializer,
)
from apps.architect.services import ArchitectService
from apps.common.pages import PAGE_PARAMETERS, page_of, paginate
from apps.members.permissions import IsTrainer, IsViewer, ViewersReadTrainersWrite
from apps.training.models import TrainingRun


class PresetView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="architect_presets",
        summary="Starting points for a new model",
        responses={200: PresetListSerializer},
    )
    def get(self, request: Request) -> Response:
        presets: list[dict[str, Any]] = ArchitectService(request.user).presets()
        return Response(PresetListSerializer({"presets": presets}).data)


class EstimateView(APIView):
    permission_classes = [IsViewer]

    @extend_schema(
        operation_id="architect_estimate",
        summary="What a design adds up to",
        description=(
            "Parameters by part, the share the vocabulary takes, and the memory to train it on "
            "this machine. When `tokenizer` names a model in the library with a larger "
            "vocabulary, the design is counted at that size, as training will build it. A "
            "design that can't be built answers 400 with `design_<reason>`."
        ),
        request=EstimateRequestSerializer,
        responses={200: EstimateSerializer},
    )
    def post(self, request: Request) -> Response:
        payload: EstimateRequestSerializer = EstimateRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        estimate: dict[str, Any] = ArchitectService(request.user).estimate(
            payload.validated_data["design"],
            payload.validated_data["seq_len"],
            payload.validated_data["batch"],
            payload.validated_data["tokenizer"],
        )
        return Response(EstimateSerializer(estimate).data)


class DraftListView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="architect_drafts",
        summary="Saved designs",
        parameters=PAGE_PARAMETERS,
        responses={200: page_of(DraftSerializer)},
    )
    def get(self, request: Request) -> Response:
        service: ArchitectService = ArchitectService(request.user)

        def render(drafts: Iterable[ArchitectureDraft]) -> list[Any]:
            return [DraftSerializer(service.describe(draft)).data for draft in drafts]

        return paginate(request, self, service.listing(), render)

    @extend_schema(
        summary="Save a design", request=NewDraftSerializer, responses={201: DraftSerializer}
    )
    def post(self, request: Request) -> Response:
        payload: NewDraftSerializer = NewDraftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service: ArchitectService = ArchitectService(request.user)
        draft: ArchitectureDraft = service.create(**payload.validated_data)
        return Response(
            DraftSerializer(service.describe(draft)).data, status=status.HTTP_201_CREATED
        )


class DraftDetailView(APIView):
    permission_classes = [ViewersReadTrainersWrite]

    @extend_schema(
        operation_id="architect_draft", summary="One design", responses={200: DraftSerializer}
    )
    def get(self, request: Request, draft_id: str) -> Response:
        service: ArchitectService = ArchitectService(request.user)
        return Response(DraftSerializer(service.describe(service.find(draft_id))).data)

    @extend_schema(
        summary="Change a design", request=DraftChangeSerializer, responses={200: DraftSerializer}
    )
    def patch(self, request: Request, draft_id: str) -> Response:
        payload: DraftChangeSerializer = DraftChangeSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        service: ArchitectService = ArchitectService(request.user)
        draft: ArchitectureDraft = service.change(draft_id, **payload.validated_data)
        return Response(DraftSerializer(service.describe(draft)).data)

    @extend_schema(summary="Remove a design", request=None, responses={204: None})
    def delete(self, request: Request, draft_id: str) -> Response:
        ArchitectService(request.user).remove(draft_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainDesignView(APIView):
    permission_classes = [IsTrainer]

    @extend_schema(
        operation_id="architect_train",
        summary="Train a design from nothing",
        description=(
            "Makes a project for the new model and queues its training on the approved replies "
            "of the projects named and the library datasets chosen. When it finishes, the model "
            "joins the library and becomes the project's base, so it can be chatted with and "
            "fine-tuned like any other."
        ),
        request=TrainDesignSerializer,
        responses={202: TrainStartedSerializer},
    )
    def post(self, request: Request, draft_id: str) -> Response:
        payload: TrainDesignSerializer = TrainDesignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run: TrainingRun = ArchitectService(request.user).train(
            draft_id,
            name=payload.validated_data["name"],
            corrections_from=[str(source) for source in payload.validated_data["corrections_from"]],
            datasets=payload.validated_data.get("datasets", []),
            hyperparams=payload.validated_data.get("hyperparams"),
        )
        started: dict[str, Any] = {"project": run.project_id, "run": run.pk}
        return Response(TrainStartedSerializer(started).data, status=status.HTTP_202_ACCEPTED)
