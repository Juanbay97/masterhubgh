"""Compatibility wrapper for legacy import paths.

Single source of truth: `hubgh.api.my_profile`.
Keep this module as a thin re-export to preserve backward compatibility.
"""

from hubgh.api.my_profile import get_summary, get_time_summary  # noqa: F401

__all__ = ["get_summary", "get_time_summary"]
