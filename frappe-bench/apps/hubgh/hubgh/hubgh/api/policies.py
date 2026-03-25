"""Compatibility wrapper for legacy import paths.

Single source of truth: `hubgh.api.policies`.
Keep this alias module to avoid breaking existing imports until retirement.
"""

from hubgh.api.policies import search  # noqa: F401

__all__ = ["search"]
