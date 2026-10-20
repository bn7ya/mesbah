from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

MESSAGES: dict[str, str] = {
    "missing": "This is needed.",
    "invalid": "This needs a whole number.",
    "out_of_range": "This is outside what Mesbah can build.",
    "not_divisible": "The hidden size must divide evenly between the heads.",
    "odd_head_dim": "Each head needs an even width.",
    "too_many_active_experts": "A token can't use more experts than the model has.",
    "tied_only": "An encoder-decoder shares its input and output embeddings.",
}


class DesignRefused(ValidationError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code: str = "design_invalid"
    default_detail = "This design can't be built."

    def __init__(self, code: str, field: str) -> None:
        super().__init__({field: [MESSAGES.get(code, str(self.default_detail))]})
        self.default_code = f"design_{code}"


class TokenizerNeeded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "tokenizer_needed"
    default_detail = "Name the tokenizer the new model will reuse, such as Qwen/Qwen3-0.6B."
