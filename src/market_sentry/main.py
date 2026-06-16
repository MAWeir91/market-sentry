"""Minimal entry point for Market Sentry Phase 0."""

from market_sentry.config import load_config


def main() -> None:
    """Validate that the scaffold entry point can load safe configuration."""

    load_config()


if __name__ == "__main__":
    main()
