"""Offline FMP float/reference request and parsing skeleton.

FMP is planned for float/reference data only. It is not an intraday market
movement source and does not produce scanner-ready StockCandidate objects by
itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FMP_BASE_URL = "https://financialmodelingprep.com"
SHARES_FLOAT_PATH = "/stable/shares-float"


@dataclass(frozen=True)
class FMPReferenceSettings:
    """Settings for shaping future FMP reference-data requests."""

    api_key: str | None = field(default=None, repr=False)
    base_url: str = FMP_BASE_URL


@dataclass(frozen=True)
class FMPRequest:
    """Deterministic request shape for future FMP HTTP execution."""

    path: str
    params: dict[str, str] = field(repr=False)


@dataclass(frozen=True)
class FMPFloatData:
    """Normalized FMP float/reference data from a fixture."""

    symbol: str
    float_shares: int
    outstanding_shares: int | None = None
    date: str | None = None


def _normalize_symbol(symbol: str | None) -> str:
    if symbol is None:
        return ""
    return symbol.strip().upper()


def build_auth_params(settings: FMPReferenceSettings) -> dict[str, str]:
    """Build optional auth params without logging or validating secrets."""

    if not settings.api_key:
        return {}
    return {"apikey": settings.api_key}


def build_shares_float_request(
    symbol: str | None,
    settings: FMPReferenceSettings,
) -> FMPRequest:
    """Build a shares-float request shape without sending it."""

    params = {"symbol": _normalize_symbol(symbol)}
    params.update(build_auth_params(settings))
    return FMPRequest(path=SHARES_FLOAT_PATH, params=params)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        converted = int(float(value))
    except (TypeError, ValueError):
        return None
    return converted


def normalize_float_shares(value: Any) -> int | None:
    """Return a positive integer float value or None."""

    converted = _to_int(value)
    if converted is None or converted <= 0:
        return None
    return converted


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _candidate_records(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        return [payload]
    return []


def parse_shares_float_response(
    payload: list[dict[str, Any]] | dict[str, Any],
    symbol: str,
) -> FMPFloatData | None:
    """Parse FMP shares-float fixture data for one symbol."""

    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return None

    for record in _candidate_records(payload):
        record_symbol = _normalize_symbol(record.get("symbol"))
        if record_symbol != normalized_symbol:
            continue

        float_shares = normalize_float_shares(
            _first_present(record, ("floatShares", "freeFloat", "float"))
        )
        if float_shares is None:
            return None

        outstanding_shares = _to_int(
            _first_present(record, ("outstandingShares", "sharesOutstanding"))
        )
        if outstanding_shares is not None and outstanding_shares <= 0:
            outstanding_shares = None

        date_value = record.get("date")
        return FMPFloatData(
            symbol=normalized_symbol,
            float_shares=float_shares,
            outstanding_shares=outstanding_shares,
            date=str(date_value) if date_value is not None else None,
        )

    return None


def is_valid_low_float_reference(
    data: FMPFloatData,
    *,
    min_float: int = 500_000,
    max_float: int = 10_000_000,
) -> bool:
    """Return whether reference float falls in the current low-float band."""

    return min_float <= data.float_shares <= max_float
