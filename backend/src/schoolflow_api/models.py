"""Every table class, imported in one place.

Alembic compares Base.metadata with the real database to find changes, so it
must see every model. Each feature module's models.py is imported here.
"""

from schoolflow_api.db import Base

__all__ = ["Base"]
