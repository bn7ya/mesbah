from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class HuggingFaceTokenRejected(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "hf_token_rejected"
    default_detail = "HuggingFace did not accept this token."


class HuggingFaceUnreachable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "hf_unreachable"
    default_detail = "HuggingFace can't be reached right now. Try again."


class UnknownGpu(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unknown_gpu"
    default_detail = "That GPU isn't on this machine."
