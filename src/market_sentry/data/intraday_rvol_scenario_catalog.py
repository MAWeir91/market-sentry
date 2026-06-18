"""Deterministic offline scenario fixtures for intraday RVOL composition.

The catalog supplies raw fixture data only. Existing offline test layers own
RVOL calculation, candidate composition, and skip diagnostics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.intraday_rvol_harness import (
    IntradayRelativeVolumeHarnessInput,
)


@dataclass(frozen=True)
class OfflineIntradayRvolScenarioFixture:
    """Raw fixture data for one offline intraday RVOL candidate scenario."""

    name: str
    description: str
    requested_symbols: tuple[str, ...]
    rvol_fixture_inputs: tuple[IntradayRelativeVolumeHarnessInput, ...]
    snapshots_by_symbol: Mapping[str, AlpacaSnapshot]
    float_data_by_symbol: Mapping[str, FMPFloatData | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_symbols", tuple(self.requested_symbols))
        object.__setattr__(
            self,
            "rvol_fixture_inputs",
            tuple(self.rvol_fixture_inputs),
        )
        object.__setattr__(
            self,
            "snapshots_by_symbol",
            MappingProxyType(dict(self.snapshots_by_symbol)),
        )
        object.__setattr__(
            self,
            "float_data_by_symbol",
            MappingProxyType(dict(self.float_data_by_symbol)),
        )


_CUTOFF = datetime(2026, 1, 2, 9, 32)
_PRE_CUTOFF = datetime(2026, 1, 2, 9, 31)
_AFTER_CUTOFF = datetime(2026, 1, 2, 9, 33)
_BUCKET = "09:32"
_HISTORICAL_SESSION_COUNT = 20
_SCENARIO_ORDER = (
    "valid_runner",
    "missing_rvol_invalid_history",
    "missing_snapshot",
    "invalid_float",
    "duplicate_symbols",
    "all_skipped",
)


def _bars(start_volume: int) -> tuple[IntradayVolumeBar, ...]:
    return (
        IntradayVolumeBar(_PRE_CUTOFF, start_volume),
        IntradayVolumeBar(_CUTOFF, start_volume * 2),
        IntradayVolumeBar(_AFTER_CUTOFF, start_volume * 3),
    )


def _series(
    symbol: str,
    session_id: str,
    *,
    start_volume: int = 100,
    bars: tuple[IntradayVolumeBar, ...] | None = None,
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=_BUCKET,
        cutoff_timestamp=_CUTOFF,
        bars=bars if bars is not None else _bars(start_volume),
    )


def _history(
    symbol: str,
    *,
    start_volume: int = 100,
    invalid_first_series: bool = False,
) -> tuple[IntradayVolumeSeriesInput, ...]:
    series_inputs: list[IntradayVolumeSeriesInput] = []
    for index in range(_HISTORICAL_SESSION_COUNT):
        bars = (
            (
                IntradayVolumeBar(_PRE_CUTOFF, 0),
                IntradayVolumeBar(_CUTOFF, start_volume * 2),
                IntradayVolumeBar(_AFTER_CUTOFF, start_volume * 3),
            )
            if invalid_first_series and index == 0
            else None
        )
        series_inputs.append(
            _series(
                symbol,
                f"{symbol}-hist-{index + 1:02d}",
                start_volume=start_volume,
                bars=bars,
            )
        )
    return tuple(series_inputs)


def _rvol_input(
    symbol: str,
    *,
    current_start_volume: int = 200,
    history_start_volume: int = 100,
    invalid_history: bool = False,
) -> IntradayRelativeVolumeHarnessInput:
    return IntradayRelativeVolumeHarnessInput(
        current_series=_series(
            symbol,
            f"{symbol}-current",
            start_volume=current_start_volume,
        ),
        historical_series=_history(
            symbol,
            start_volume=history_start_volume,
            invalid_first_series=invalid_history,
        ),
    )


def _snapshot(symbol: str, *, price: float = 4.0) -> AlpacaSnapshot:
    return AlpacaSnapshot(
        symbol=symbol,
        price=price,
        daily_volume=1_200_000,
        high_of_day=price + 0.25,
        previous_close=2.0,
    )


def _float(symbol: str, *, float_shares: int = 1_500_000) -> FMPFloatData:
    return FMPFloatData(
        symbol=symbol,
        float_shares=float_shares,
        outstanding_shares=12_000_000,
        date="2026-01-02",
    )


def _build_scenarios() -> tuple[OfflineIntradayRvolScenarioFixture, ...]:
    return (
        OfflineIntradayRvolScenarioFixture(
            name="valid_runner",
            description="Valid intraday RVOL, snapshot, and float data produce a candidate.",
            requested_symbols=("RUNR",),
            rvol_fixture_inputs=(_rvol_input("RUNR", current_start_volume=240),),
            snapshots_by_symbol={"RUNR": _snapshot("RUNR", price=4.8)},
            float_data_by_symbol={"RUNR": _float("RUNR")},
        ),
        OfflineIntradayRvolScenarioFixture(
            name="missing_rvol_invalid_history",
            description="Invalid historical intraday data prevents usable RVOL.",
            requested_symbols=("BADH",),
            rvol_fixture_inputs=(_rvol_input("BADH", invalid_history=True),),
            snapshots_by_symbol={"BADH": _snapshot("BADH")},
            float_data_by_symbol={"BADH": _float("BADH")},
        ),
        OfflineIntradayRvolScenarioFixture(
            name="missing_snapshot",
            description="Valid RVOL and float data with no matching snapshot.",
            requested_symbols=("NOSNAP",),
            rvol_fixture_inputs=(_rvol_input("NOSNAP", current_start_volume=260),),
            snapshots_by_symbol={},
            float_data_by_symbol={"NOSNAP": _float("NOSNAP")},
        ),
        OfflineIntradayRvolScenarioFixture(
            name="invalid_float",
            description="Valid RVOL and snapshot with explicitly invalid float data.",
            requested_symbols=("BADFLT",),
            rvol_fixture_inputs=(_rvol_input("BADFLT", current_start_volume=280),),
            snapshots_by_symbol={"BADFLT": _snapshot("BADFLT")},
            float_data_by_symbol={"BADFLT": _float("BADFLT", float_shares=0)},
        ),
        OfflineIntradayRvolScenarioFixture(
            name="duplicate_symbols",
            description="Duplicate normalized symbol inputs retain the last successful RVOL.",
            requested_symbols=("DUPL",),
            rvol_fixture_inputs=(
                _rvol_input("dupl", current_start_volume=220),
                _rvol_input("DUPL", invalid_history=True),
                _rvol_input(" DUPL ", current_start_volume=520),
            ),
            snapshots_by_symbol={"DUPL": _snapshot("DUPL", price=5.2)},
            float_data_by_symbol={"DUPL": _float("DUPL")},
        ),
        OfflineIntradayRvolScenarioFixture(
            name="all_skipped",
            description="Multiple requested symbols produce only lower-level and builder diagnostics.",
            requested_symbols=("BADH", "NOSNAP", "BADFLT"),
            rvol_fixture_inputs=(
                _rvol_input("BADH", invalid_history=True),
                _rvol_input("NOSNAP", current_start_volume=260),
                _rvol_input("BADFLT", current_start_volume=280),
            ),
            snapshots_by_symbol={
                "BADH": _snapshot("BADH"),
                "BADFLT": _snapshot("BADFLT"),
            },
            float_data_by_symbol={
                "BADH": _float("BADH"),
                "NOSNAP": _float("NOSNAP"),
                "BADFLT": _float("BADFLT", float_shares=0),
            },
        ),
    )


def get_offline_intraday_rvol_scenarios() -> tuple[OfflineIntradayRvolScenarioFixture, ...]:
    """Return all offline intraday RVOL scenario fixtures in stable order."""

    return _build_scenarios()


def get_offline_intraday_rvol_scenario(
    name: str,
) -> OfflineIntradayRvolScenarioFixture:
    """Return a scenario fixture by exact stable name."""

    for scenario in get_offline_intraday_rvol_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(f"Unknown offline intraday RVOL scenario: {name}")


def offline_intraday_rvol_scenario_names() -> tuple[str, ...]:
    """Return stable scenario names in catalog order."""

    return _SCENARIO_ORDER
