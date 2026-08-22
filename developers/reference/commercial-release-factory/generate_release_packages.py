#!/usr/bin/env python3
"""Compatibility entrypoint for Commercial Release Factory v2."""
from commercial_release_factory import FactoryError as ReleaseFactoryError, generate, main

__all__ = ["ReleaseFactoryError", "generate"]

if __name__ == "__main__":
    raise SystemExit(main())
