from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class BaseModelNotReady(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "base_model_not_ready"
    default_detail = "Choose a model that has finished downloading."
