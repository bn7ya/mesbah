from __future__ import annotations

from rest_framework.parsers import JSONParser


class AnyMediaTypeJSONParser(JSONParser):
    media_type = "*/*"
