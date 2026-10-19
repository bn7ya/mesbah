from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

type Json = dict[str, object]

WAIT_SECONDS: float = 120.0
POLL_SECONDS: float = 0.5


class ClientError(Exception):
    def __init__(self, method: str, path: str, status: int, body: str) -> None:
        super().__init__(f"{method} {path} answered {status}: {body[:300]}")
        self.status: int = status


@dataclass(frozen=True)
class Answer:
    status: int
    content_type: str
    body: bytes

    def json(self) -> Json:
        parsed: object = json.loads(self.body) if self.body else {}
        return parsed if isinstance(parsed, dict) else {"results": parsed}


@dataclass
class Client:
    base_url: str
    jar: http.cookiejar.CookieJar = field(default_factory=http.cookiejar.CookieJar)
    bearer: str | None = None

    def __post_init__(self) -> None:
        self.opener: urllib.request.OpenerDirector = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def csrf(self) -> str:
        return next((cookie.value or "" for cookie in self.jar if cookie.name == "csrftoken"), "")

    def send(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        content_type: str = "application/json",
    ) -> Answer:
        headers: dict[str, str] = {"Referer": f"{self.base_url}/"}
        if body is not None:
            headers["Content-Type"] = content_type
        if method != "GET":
            headers["X-CSRFToken"] = self.csrf()
        if self.bearer:
            headers["Authorization"] = f"Bearer {self.bearer}"
        request: urllib.request.Request = urllib.request.Request(  # noqa: S310 - a local address
            f"{self.base_url}{path}", data=body, method=method, headers=headers
        )
        try:
            with self.opener.open(request, timeout=WAIT_SECONDS) as response:
                return Answer(
                    int(response.status), response.headers.get_content_type(), response.read()
                )
        except urllib.error.HTTPError as error:
            return Answer(error.code, error.headers.get_content_type(), error.read())

    def call(self, method: str, path: str, data: object = None) -> Json:
        body: bytes | None = None if data is None else json.dumps(data).encode()
        answer: Answer = self.send(method, path, body)
        if not 200 <= answer.status < 300:
            raise ClientError(method, path, answer.status, answer.body.decode(errors="replace"))
        return answer.json()

    def get(self, path: str) -> Json:
        return self.call("GET", path)

    def post(self, path: str, data: object = None) -> Json:
        return self.call("POST", path, {} if data is None else data)

    def patch(self, path: str, data: object) -> Json:
        return self.call("PATCH", path, data)

    def upload(self, path: str, name: str, content: bytes, fields: dict[str, str]) -> Json:
        boundary: str = uuid.uuid4().hex
        disposition: str = "Content-Disposition: form-data; name"
        parts: list[bytes] = [
            f'--{boundary}\r\n{disposition}="{key}"\r\n\r\n{value}\r\n'.encode()
            for key, value in fields.items()
        ]
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        answer: Answer = self.send(
            "POST", path, b"".join(parts), f"multipart/form-data; boundary={boundary}"
        )
        if not 200 <= answer.status < 300:
            raise ClientError("POST", path, answer.status, answer.body.decode(errors="replace"))
        return answer.json()

    def sign_in(self, username: str, password: str) -> Json:
        self.get("/api/auth/csrf/")
        return self.post("/api/auth/login/", {"username": username, "password": password})

    def until(self, path: str, done: Callable[[Json], bool], seconds: float = WAIT_SECONDS) -> Json:
        deadline: float = time.monotonic() + seconds
        last: Json = self.get(path)
        while not done(last):
            if time.monotonic() > deadline:
                raise TimeoutError(f"{path} never got there: {json.dumps(last)[:300]}")
            time.sleep(POLL_SECONDS)
            last = self.get(path)
        return last


def text(value: Json, key: str) -> str:
    found: object = value.get(key)
    if not isinstance(found, str):
        raise KeyError(f"expected a string at {key} in {json.dumps(value)[:300]}")
    return found


def items(value: Json, key: str = "results") -> list[Json]:
    found: object = value.get(key)
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []
