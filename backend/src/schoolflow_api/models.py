"""Every table class, imported in one place.

Alembic compares Base.metadata with the real database to find changes, so it
must see every model. Each feature module's models.py is imported here.
"""

from schoolflow_api.accounts import models as accounts_models
from schoolflow_api.db import Base
from schoolflow_api.platform import models as platform_models
from schoolflow_api.schools import models as schools_models

__all__ = ["Base", "accounts_models", "platform_models", "schools_models"]
