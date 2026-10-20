from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class HubUnreachable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "hf_unreachable"
    default_detail = "HuggingFace can't be reached right now. Try again."


class ModelNotFoundOnHub(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "hub_model_not_found"
    default_detail = "There is no model with that name on HuggingFace."


class ModelGated(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "hub_model_gated"
    default_detail = "This model needs a HuggingFace token with access to it."


class NotDownloadable(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "not_downloadable"
    default_detail = "This repository has no model weights Mesbah can load."


class AlreadyInLibrary(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "already_in_library"
    default_detail = "This model is already in the library."


class ModelInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "model_in_use"
    default_detail = "A project is built on this model. Remove the project first."


class NotEnoughDisk(APIException):
    status_code = status.HTTP_507_INSUFFICIENT_STORAGE
    default_code = "disk_full"
    default_detail = "There isn't enough free disk space for this model."
