"""Workaround for the huggingface_hub 1.x httpx/brotli download bug.

huggingface_hub 1.x performs downloads with ``httpx``. When ``brotlicffi`` is
installed, httpx advertises ``Accept-Encoding: br`` and decodes brotli responses
with a streaming decoder that is buggy — on some dataset/model files it raises
mid-stream::

    httpx.DecodingError: brotli: decoder process called with data when
    'can_accept_more_data()' is False

We can't change httpx's decoder, but huggingface_hub 1.x lets us supply the
``httpx.Client`` via ``set_client_factory``. Our factory advertises only
``gzip, deflate`` so the Hub never serves brotli and the broken path is never
taken. Idempotent and fully guarded: a no-op on older hub (the ``requests``-based
0.x line, which lacks this hook and isn't affected).
"""
from __future__ import annotations


def disable_httpx_brotli() -> None:
    try:
        import httpx
        from huggingface_hub.utils import _http as hf_http
    except Exception:
        return
    if not hasattr(hf_http, "set_client_factory"):
        return  # hub < 1.x (requests backend) — not affected

    def _factory():
        hooks = []
        # Preserve hub's own request hook (auth header / trace id) when present.
        base = getattr(hf_http, "hf_request_event_hook", None)
        if base is not None:
            hooks.append(base)

        def _no_brotli(request):
            request.headers["accept-encoding"] = "gzip, deflate"
        hooks.append(_no_brotli)
        return httpx.Client(event_hooks={"request": hooks},
                            follow_redirects=True, timeout=None)

    try:
        hf_http.set_client_factory(_factory)
    except Exception:
        pass
