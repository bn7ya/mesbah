from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class HubUnreachable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "hf_unreachable"
    default_detail = "HuggingFace can't be reached right now. Try again."


class DatasetNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "hub_dataset_not_found"
    default_detail = "There is no dataset with that name on HuggingFace."


class DatasetGated(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "hub_dataset_gated"
    default_detail = "This dataset needs a HuggingFace token with access to it."


class DatasetUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "hub_dataset_unavailable"
    default_detail = "HuggingFace has no ready copy of this dataset to read."


class UnknownSplit(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unknown_split"
    default_detail = "This dataset has no such subset or split."


class UnsupportedFormat(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unsupported_format"
    default_detail = "The rows of this data don't match a layout Mesbah can train on."


class MissingColumn(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "missing_column"
    default_detail = "A chosen column isn't in this data."


class UnsupportedFile(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unsupported_file"
    default_detail = "Upload a .jsonl, .json or .csv file."


class FileTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_code = "file_too_large"
    default_detail = "The file is larger than 200 MB."


class EmptyFile(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "empty_file"
    default_detail = "The file has no rows."


class NotReady(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "dataset_not_ready"
    default_detail = "This dataset hasn't finished importing."


class UploadMissing(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "upload_missing"
    default_detail = "The uploaded file is gone. Upload it again."


class NotEnoughDisk(APIException):
    status_code = status.HTTP_507_INSUFFICIENT_STORAGE
    default_code = "disk_full"
    default_detail = "There isn't enough free disk space for this dataset."


class Cancelled(Exception):
    pass
