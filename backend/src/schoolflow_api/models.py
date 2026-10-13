"""Every table class, imported in one place.

Alembic compares Base.metadata with the real database to find changes, so it
must see every model. Each feature module's models.py is imported here.
"""

from schoolflow_api.accounts import models as accounts_models
from schoolflow_api.assignments import models as assignments_models
from schoolflow_api.auth import models as auth_models
from schoolflow_api.authz import models as authz_models
from schoolflow_api.db import Base
from schoolflow_api.grading import models as grading_models
from schoolflow_api.guardians import models as guardians_models
from schoolflow_api.platform import models as platform_models
from schoolflow_api.results import models as results_models
from schoolflow_api.schools import models as schools_models
from schoolflow_api.structure import models as structure_models
from schoolflow_api.students import models as students_models

__all__ = [
    "Base",
    "accounts_models",
    "assignments_models",
    "auth_models",
    "authz_models",
    "grading_models",
    "guardians_models",
    "platform_models",
    "results_models",
    "schools_models",
    "structure_models",
    "students_models",
]
