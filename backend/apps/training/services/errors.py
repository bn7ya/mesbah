from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class BaseNotDownloaded(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "base_model_not_ready"
    default_detail = "The project's base model isn't downloaded yet."


class NothingToLearn(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "nothing_to_learn"
    default_detail = (
        "There are no approved replies to learn from yet. Correct or approve some first."
    )


class WrongParent(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "wrong_parent"
    default_detail = "That version belongs to another project."


class RunStillGoing(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "run_still_going"
    default_detail = "Stop the training before removing it."
