"""Backend services package.

Avoid importing heavy modules (like ML prediction that depends on compiled
extensions) at package import time. Consumers should import those services
explicitly to avoid bringing large C-extension deps into simple import paths.
"""

# Expose lightweight services eagerly; heavy services can be imported directly
# from their modules to allow lazy loading in runtime contexts.
from . import nba_service  # expose nba_service for external imports

__all__ = ["nba_service"]
