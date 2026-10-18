from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class MessageChanged(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "message_changed"
    default_detail = "This message changed since you opened it. Reload it and try again."


class NotEditable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "not_editable"
    default_detail = "Only a finished reply from the model can be edited."


class NoVersion(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "no_version"
    default_detail = "This project has no version to chat with."


class EmptyReply(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "empty_reply"
    default_detail = "An empty reply can't be approved."
