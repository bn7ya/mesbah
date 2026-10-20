from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class RootVersionKept(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "root_version_kept"
    default_detail = "The first version is the base model itself and stays."


class ActiveVersionKept(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "active_version_kept"
    default_detail = "Activate another version before removing this one."


class NotExportable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "not_exportable"
    default_detail = "This version can't be exported that way."


class ExportNotReady(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "export_not_ready"
    default_detail = "This export isn't ready to download."
