"""Standard-library HTTP transport for future live-provider phases.

This transport is not wired into runtime providers. It exists as injectable
infrastructure for future controlled provider work.
"""

from __future__ import annotations

import socket
from urllib import error, parse, request

from market_sentry.data.http import (
    HttpRequest,
    HttpResponse,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
)


class StdlibHttpTransport:
    """Minimal HttpTransport implementation using Python's standard library."""

    def send(self, http_request: HttpRequest) -> HttpResponse:
        method = http_request.method.upper()
        if method != "GET":
            raise HttpTransportError(f"Unsupported HTTP method: {method}.")

        url = _url_with_params(http_request.url, http_request.params)
        stdlib_request = request.Request(
            url,
            headers=dict(http_request.headers),
            method=method,
        )

        try:
            response = request.urlopen(
                stdlib_request,
                timeout=http_request.timeout_seconds,
            )
        except error.HTTPError as exc:
            raise HttpStatusError(exc.code) from exc
        except TimeoutError as exc:
            raise HttpTimeoutError("HTTP request timed out.") from exc
        except socket.timeout as exc:
            raise HttpTimeoutError("HTTP request timed out.") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise HttpTimeoutError("HTTP request timed out.") from exc
            raise HttpTransportError("HTTP request failed.") from exc

        status_code = _response_status_code(response)
        if not 200 <= status_code <= 299:
            raise HttpStatusError(status_code)

        body = response.read().decode(_response_charset(response), errors="replace")
        return HttpResponse(
            status_code=status_code,
            body=body,
            headers=_response_headers(response),
        )


def _url_with_params(url: str, params) -> str:
    parsed = parse.urlsplit(url)
    query_items = parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_items.extend((str(key), str(value)) for key, value in params.items())
    encoded_query = parse.urlencode(query_items)
    return parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            encoded_query,
            parsed.fragment,
        )
    )


def _response_status_code(response) -> int:
    if hasattr(response, "getcode"):
        return int(response.getcode())
    return int(response.status)


def _response_charset(response) -> str:
    headers = getattr(response, "headers", {})
    get_content_charset = getattr(headers, "get_content_charset", None)
    if callable(get_content_charset):
        return get_content_charset() or "utf-8"
    return "utf-8"


def _response_headers(response) -> dict[str, str]:
    headers = getattr(response, "headers", {})
    items = getattr(headers, "items", None)
    if callable(items):
        return {str(key): str(value) for key, value in items()}
    return {str(key): str(value) for key, value in dict(headers).items()}
