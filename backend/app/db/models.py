"""Every table class, imported in one place.

Alembic compares Base.metadata with the real database to find changes, so it
must see every model. Each feature module's models.py is imported here.
"""

from app.core import models as authz_models
from app.core import models as core_models
from app.db.base import Base
from app.src.accounts import models as accounts_models
from app.src.attention import models as attention_models
from app.src.audit import models as audit_models
from app.src.auth import models as auth_models
from app.src.billing import models as billing_models
from app.src.corrections import models as corrections_models
from app.src.emails import models as emails_models
from app.src.files import models as files_models
from app.src.form_class import models as form_class_models
from app.src.grading import models as grading_models
from app.src.grading import models as ratings_models
from app.src.guardians import models as guardians_models
from app.src.notices import models as notices_models
from app.src.platform_admin import models as platform_models
from app.src.reports import models as reports_models
from app.src.results import models as results_models
from app.src.schools import models as schools_models
from app.src.staff import models as assignments_models
from app.src.structure import models as structure_models
from app.src.students import models as students_models

__all__ = [
    "Base",
    "accounts_models",
    "assignments_models",
    "attention_models",
    "audit_models",
    "auth_models",
    "authz_models",
    "billing_models",
    "core_models",
    "corrections_models",
    "emails_models",
    "files_models",
    "form_class_models",
    "grading_models",
    "guardians_models",
    "notices_models",
    "platform_models",
    "ratings_models",
    "reports_models",
    "results_models",
    "schools_models",
    "structure_models",
    "students_models",
]
