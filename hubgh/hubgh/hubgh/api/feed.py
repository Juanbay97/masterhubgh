"""Compatibility wrapper for legacy import paths.

Single source of truth: `hubgh.api.feed`.
Keep this module as a thin re-export to avoid breaking existing dotted paths.
"""

from hubgh.api.feed import get_posts  # noqa: F401

__all__ = ["get_posts"]
