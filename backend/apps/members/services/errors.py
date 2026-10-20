from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class UsernameTaken(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "username_taken"
    default_detail = "That username is already in use."


class WeakPassword(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "weak_password"
    default_detail = "That password is too easy to guess."


class LastAdministrator(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "last_administrator"
    default_detail = "Mesbah needs at least one active administrator."


class OwnerLocked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "owner_locked"
    default_detail = "The owner account keeps its role and stays active."


class SelfDeactivation(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "self_deactivation"
    default_detail = "You can't deactivate your own account."
