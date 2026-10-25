"""The super admin's pages: /platform (BUILD_PROMPT 9.2d; SPEC F03 rule 5, F24, F25).

Every route checks the super admin with the chain (`require(...)`) and works
through the platform session (`PlatformDb`, role app_platform). Every change
writes an audit event in the same transaction; events about one school carry
that school, so its Activity tab can list them. Emails are queued in the
outbox; links in them are made by the sender at send time (D-081), so no
token or password is ever stored or sent from here.

Login support reaches school admins only: the platform role cannot see any
other account, and every action first finds the person among the school's
admins, so a teacher's id is simply not found (AT-29.2).
"""

import json
import uuid
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.core.security import issue_temporary_password
from app.src.platform_admin import settings_model as settings_model
from app.src.platform_admin.schemas import (
    AdminRow,
    AuditRow,
    Available,
    ChangeCode,
    Code,
    Created,
    CreateSchool,
    Detail,
    EditSchool,
    EmailRow,
    Features,
    Levels,
    LevelsChange,
    LevelsResult,
    Limit,
    NewEmail,
    PaymentRow,
    ResetLink,
    SchoolDetail,
    SchoolDetails,
    SchoolRow,
    Subscription,
    Suspend,
    TemporaryPassword,
    Usage,
    Username,
)
from app.src.schools.models import AssessmentMode, Feature, Level

# F25 rule 2: what each school type switches on.
PRESETS: dict[str, Levels] = {
    "nursery_primary": Levels(nursery=True, primary=True, secondary=False),
    "secondary_only": Levels(nursery=False, primary=False, secondary=True),
    "all_levels": Levels(nursery=True, primary=True, secondary=True),
}

TOGGLE_LEVELS = {
    "nursery": (Level.NURSERY,),
    "primary": (Level.PRIMARY,),
    "secondary": (Level.JUNIOR_SECONDARY, Level.SENIOR_SECONDARY),
}

CODE_CHANGE_WARNING = "Students must use the new code. The old code stops working."


# --- helpers -----------------------------------------------------------------------------
def audit(
    db: Session,
    school_id: uuid.UUID | None,
    action: str,
    *,
    target: tuple[str, uuid.UUID] | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    db.execute(
        text(
            "insert into audit_events (school_id, actor_role, action, target_table, target_id,"
            " old_values, new_values, reason) values (:school, 'super_admin', :action, :table,"
            " :target, cast(:old as jsonb), cast(:new as jsonb), :reason)"
        ),
        {
            "school": school_id,
            "action": action,
            "table": target[0] if target else None,
            "target": target[1] if target else None,
            "old": json.dumps(old) if old is not None else None,
            "new": json.dumps(new) if new is not None else None,
            "reason": reason,
        },
    )


def queue_email(
    db: Session, school_id: uuid.UUID, template: str, to: str, data: dict[str, Any]
) -> None:
    db.execute(
        text(
            "insert into email_outbox (school_id, type, to_address, template, template_data,"
            " priority, idempotency_key) values (:school, :template, :to, :template,"
            " cast(:data as jsonb), 1, :key)"
        ),
        {
            "school": school_id,
            "template": template,
            "to": to,
            "data": json.dumps(data),
            # One email per request: a resend is a new event (D-080).
            "key": f"{template}:{school_id}:{uuid.uuid4()}",
        },
    )


def taken(field: str, message: str, code: str) -> ProblemError:
    """A 409 that names the field, as a form shows it."""
    return ProblemError(
        409,
        message,
        code=code,
        errors=[{"loc": ["body", *field.split(".")], "msg": message, "type": code}],
    )


def school_row(db: Session, school_id: uuid.UUID) -> Any:
    return found(
        db.execute(
            text(
                "select id, code, name, status, school_type, city, state, email, phone,"
                " address, country, colour from schools where id = :id"
            ),
            {"id": school_id},
        ).first()
    )


def levels_of(db: Session, school_id: uuid.UUID) -> Levels:
    enabled = {
        str(row.level): bool(row.enabled)
        for row in db.execute(
            text("select level, enabled from school_levels where school_id = :id"),
            {"id": school_id},
        )
    }
    return Levels(
        nursery=enabled.get(Level.NURSERY, False),
        primary=enabled.get(Level.PRIMARY, False),
        secondary=enabled.get(Level.JUNIOR_SECONDARY, False),
    )


def features_of(db: Session, school_id: uuid.UUID) -> Features:
    rows = db.execute(
        text("select feature, enabled from school_features where school_id = :id"),
        {"id": school_id},
    )
    return Features.model_validate({str(r.feature): bool(r.enabled) for r in rows})


def school_type_for(levels: Levels) -> str:
    return next((name for name, preset in PRESETS.items() if preset == levels), "custom")


def school_detail(db: Session, school_id: uuid.UUID) -> SchoolDetail:
    row = school_row(db, school_id)
    subscription = db.execute(
        text("select billing_enabled, status from school_subscriptions where school_id = :id"),
        {"id": school_id},
    ).first()
    return SchoolDetail(
        id=str(row.id),
        code=row.code,
        name=row.name,
        status=row.status,
        school_type=row.school_type,
        city=row.city,
        state=row.state,
        email=row.email,
        phone=row.phone,
        address=row.address,
        country=row.country,
        colour=row.colour,
        features=features_of(db, school_id),
        levels=levels_of(db, school_id),
        subscription=Subscription(
            billing_enabled=subscription.billing_enabled, status=subscription.status
        )
        if subscription
        else None,
    )


def code_taken(db: Session, code: str) -> bool:
    return bool(
        db.scalar(text("select exists (select 1 from schools where code = :c)"), {"c": code})
    )


def activation_data(user: Any, school: Any) -> dict[str, Any]:
    """What the welcome email needs (F24 rule 1): never a password or a link."""
    return {
        "user_id": str(user.id),
        "full_name": user.full_name,
        "username": user.username,
        "school_code": school.code,
        "school_name": school.name,
    }


def check_code(
    code: Code,
    _: Principal,
    db: Session,
) -> Available:
    return Available(available=not code_taken(db, code))


def check_username(
    username: Username,
    _: Principal,
    db: Session,
) -> Available:
    used = db.scalar(text("select platform_username_taken(:u)"), {"u": username})
    return Available(available=not used)


def create_school(
    body: CreateSchool,
    _: Principal,
    db: Session,
) -> Created:
    if code_taken(db, body.code):
        raise taken("code", "This school code is taken.", "code_taken")
    principal = body.principal
    if db.scalar(text("select platform_username_taken(:u)"), {"u": principal.username}):
        raise taken("principal.username", "This username is taken.", "username_taken")
    if db.scalar(text("select platform_email_taken(:e)"), {"e": principal.email}):
        raise taken("principal.email", "This email is already used.", "email_taken")

    school_id: uuid.UUID = db.scalar(
        text(
            "insert into schools (name, email, phone, address, city, state, country, code,"
            " colour, school_type) values (:name, :email, :phone, :address, :city, :state,"
            " :country, :code, :colour, :school_type) returning id"
        ),
        body.model_dump(
            include={
                "name",
                "email",
                "phone",
                "address",
                "city",
                "state",
                "country",
                "code",
                "colour",
                "school_type",
            }
        ),
    )
    for feature, enabled in body.features.model_dump().items():
        db.execute(
            text("insert into school_features (school_id, feature, enabled) values (:s, :f, :e)"),
            {"s": school_id, "f": feature, "e": enabled},
        )
    preset = PRESETS[body.school_type]
    for toggle, levels in TOGGLE_LEVELS.items():
        for level in levels:
            early = level in {Level.NURSERY, Level.PRIMARY}
            db.execute(
                text(
                    "insert into school_levels (school_id, level, enabled, assessment_mode,"
                    " head_title) values (:s, :l, :e, :mode, :head)"
                ),
                {
                    "s": school_id,
                    "l": level.value,
                    "e": getattr(preset, toggle),
                    "mode": (
                        AssessmentMode.SKILL_RATINGS
                        if level == Level.NURSERY
                        else AssessmentMode.SCORES
                    ).value,
                    "head": "Head teacher" if early else "Principal",
                },
            )
    billing = body.billing == "on"
    db.execute(
        text(
            "insert into school_subscriptions (school_id, billing_enabled, status)"
            " values (:s, :on, :status)"
        ),
        {"s": school_id, "on": billing, "status": "active" if billing else "free_pilot"},
    )
    # The id is made here: the platform sees an account only once it is a school admin.
    user_id = uuid.uuid4()
    db.execute(
        text(
            "insert into users (id, full_name, username, email)"
            " values (:id, :full_name, :username, :email)"
        ),
        {"id": user_id, **principal.model_dump()},
    )
    db.execute(
        text(
            "insert into school_memberships (user_id, school_id, role, is_primary, status)"
            " values (:u, :s, 'school_admin', true, 'active')"
        ),
        {"u": user_id, "s": school_id},
    )

    school = school_row(db, school_id)
    user = db.execute(
        text("select id, full_name, username from users where id = :id"), {"id": user_id}
    ).one()
    queue_email(db, school_id, "activation", principal.email, activation_data(user, school))
    queue_email(
        db,
        school_id,
        "school_setup",
        body.email,
        {"school_name": body.name, "school_code": body.code, "login_path": f"/login/{body.code}"},
    )
    audit(
        db,
        school_id,
        "schools.create",
        target=("schools", school_id),
        new={
            "code": body.code,
            "school_type": body.school_type,
            "billing": body.billing,
            "principal_username": principal.username,
        },
    )
    return Created(id=str(school_id), code=body.code)


def list_schools(
    _: Principal,
    db: Session,
    q: str | None = None,
    status: str | None = None,
) -> list[SchoolRow]:
    rows = db.execute(
        text(
            "select id, code, name, status, school_type, city, state from schools"
            " where (cast(:q as text) is null or name ilike '%' || :q || '%'"
            "        or code ilike '%' || :q || '%')"
            " and (cast(:status as text) is null or status = :status)"
            " order by code"
        ),
        {"q": q.replace("%", "").replace("_", "") if q else None, "status": status},
    )
    return [
        SchoolRow(
            id=str(r.id),
            code=r.code,
            name=r.name,
            status=r.status,
            school_type=r.school_type,
            city=r.city,
            state=r.state,
        )
        for r in rows
    ]


def get_school(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> SchoolDetail:
    return school_detail(db, school_id)


def edit_school(
    school_id: uuid.UUID,
    body: EditSchool,
    _: Principal,
    db: Session,
) -> SchoolDetail:
    row = school_row(db, school_id)
    fields = ("name", "email", "phone", "address", "city", "state", "country", "colour")
    current = {field: getattr(row, field) for field in fields}
    wanted = {**current, **body.model_dump(exclude_none=True)}
    try:
        SchoolDetails.model_validate(wanted)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    changed = {field: value for field, value in wanted.items() if current[field] != value}
    if changed:
        assignments = ", ".join(f"{field} = :{field}" for field in changed)
        db.execute(
            text(f"update schools set {assignments} where id = :id"),  # noqa: S608 (fixed names)
            {**changed, "id": school_id},
        )
        audit(
            db,
            school_id,
            "schools.update",
            target=("schools", school_id),
            old={field: current[field] for field in changed},
            new=changed,
        )
    return school_detail(db, school_id)


def change_code(
    school_id: uuid.UUID,
    body: ChangeCode,
    _: Principal,
    db: Session,
) -> SchoolRow:
    row = school_row(db, school_id)
    if body.code != row.code:
        if code_taken(db, body.code):
            raise taken("code", "This school code is taken.", "code_taken")
        if not body.confirm:
            raise ProblemError(
                409, "Confirm the new school code", CODE_CHANGE_WARNING, code="confirmation_needed"
            )
        db.execute(
            text("update schools set code = :c where id = :id"), {"c": body.code, "id": school_id}
        )
        audit(
            db,
            school_id,
            "schools.change_code",
            target=("schools", school_id),
            old={"code": row.code},
            new={"code": body.code},
        )
    row = school_row(db, school_id)
    return SchoolRow(
        id=str(row.id),
        code=row.code,
        name=row.name,
        status=row.status,
        school_type=row.school_type,
        city=row.city,
        state=row.state,
    )


def suspend(
    school_id: uuid.UUID,
    body: Suspend,
    _: Principal,
    db: Session,
) -> None:
    school_row(db, school_id)
    db.execute(text("update schools set status = 'suspended' where id = :id"), {"id": school_id})
    audit(
        db,
        school_id,
        "schools.suspend",
        target=("schools", school_id),
        new={"status": "suspended"},
        reason=body.reason,
    )


def reactivate(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> None:
    school_row(db, school_id)
    db.execute(text("update schools set status = 'active' where id = :id"), {"id": school_id})
    audit(
        db, school_id, "schools.reactivate", target=("schools", school_id), new={"status": "active"}
    )


def resend_setup_email(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> Detail:
    row = school_row(db, school_id)
    queue_email(
        db,
        school_id,
        "school_setup",
        row.email,
        {"school_name": row.name, "school_code": row.code, "login_path": f"/login/{row.code}"},
    )
    audit(db, school_id, "schools.setup_email", target=("schools", school_id))
    return Detail(detail="Set-up email queued.")


def usage(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> Usage:
    school_row(db, school_id)
    row = db.execute(text("select * from platform_school_usage(:s)"), {"s": school_id}).one()
    return Usage(
        students=row.students,
        staff=row.staff,
        parents=row.parents,
        results_published=row.results_published,
        last_activity=row.last_activity,
    )


AUDIT_SELECT = (
    "select a.id, a.school_id, u.full_name as actor_name, a.actor_role, a.action,"
    " a.target_table, a.target_id, a.old_values, a.new_values, a.reason, a.created_at"
    " from audit_events a left join users u on u.id = a.actor_id"
)


def audit_rows(rows: Any) -> list[AuditRow]:
    return [
        AuditRow(
            id=str(r.id),
            school_id=str(r.school_id) if r.school_id else None,
            actor_name=r.actor_name,
            actor_role=r.actor_role,
            action=r.action,
            target_table=r.target_table,
            target_id=str(r.target_id) if r.target_id else None,
            old_values=r.old_values,
            new_values=r.new_values,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


def activity(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
    limit: Limit = 50,
) -> list[AuditRow]:
    """F24 rule 2: the school's platform-level events (super admin and system)."""
    school_row(db, school_id)
    return audit_rows(
        db.execute(
            text(
                f"{AUDIT_SELECT} where a.school_id = :s"
                " and a.actor_role in ('super_admin', 'system')"
                " order by a.created_at desc, a.id limit :limit"
            ),
            {"s": school_id, "limit": limit},
        )
    )


def set_features(
    school_id: uuid.UUID,
    body: Features,
    _: Principal,
    db: Session,
) -> Features:
    school_row(db, school_id)
    current = features_of(db, school_id).model_dump()
    wanted = body.model_dump()
    changed = {name: value for name, value in wanted.items() if current[name] != value}
    for name, value in changed.items():
        db.execute(
            text("update school_features set enabled = :e where school_id = :s and feature = :f"),
            {"e": value, "s": school_id, "f": Feature(name).value},
        )
    if changed:
        audit(
            db,
            school_id,
            "features.update",
            target=("schools", school_id),
            old={name: current[name] for name in changed},
            new=changed,
        )
    return features_of(db, school_id)


def set_levels(
    school_id: uuid.UUID,
    body: LevelsChange,
    _: Principal,
    db: Session,
) -> LevelsResult:
    school_row(db, school_id)
    wanted = Levels(nursery=body.nursery, primary=body.primary, secondary=body.secondary)
    if not (wanted.nursery or wanted.primary or wanted.secondary):
        raise ProblemError(
            422, "At least one report card level must stay on.", code="at_least_one_level"
        )
    current = levels_of(db, school_id)
    turned_off = [
        level
        for toggle, levels in TOGGLE_LEVELS.items()
        if getattr(current, toggle) and not getattr(wanted, toggle)
        for level in levels
    ]
    if turned_off and not body.confirm:
        classes = [
            str(name)
            for level in turned_off
            for name in db.scalars(
                text("select * from platform_unpublished_classes(:s, :l)"),
                {"s": school_id, "l": level.value},
            )
        ]
        if classes:
            raise ProblemError(
                409,
                "Confirm turning this level off",
                f"Unpublished results this term: {', '.join(classes)}.",
                code="confirmation_needed",
            )
    for toggle, levels in TOGGLE_LEVELS.items():
        for level in levels:
            db.execute(
                text("update school_levels set enabled = :e where school_id = :s and level = :l"),
                {"e": getattr(wanted, toggle), "s": school_id, "l": level.value},
            )
    school_type = school_type_for(wanted)
    db.execute(
        text("update schools set school_type = :t where id = :id"),
        {"t": school_type, "id": school_id},
    )
    if wanted != current:
        audit(
            db,
            school_id,
            "report_card_levels.update",
            target=("schools", school_id),
            old=current.model_dump(),
            new=wanted.model_dump(),
        )
    return LevelsResult(levels=wanted, school_type=school_type)


# --- school admins and their login support (F03 rule 5) ------------------------------
ADMIN_SELECT = (
    "select u.id, u.full_name, u.username, u.email, u.is_active,"
    " u.password_hash is not null as activated, m.is_primary, m.status as membership_status"
    " from school_memberships m join users u on u.id = m.user_id"
    " where m.school_id = :s and m.role = 'school_admin'"
)


def admin_of(db: Session, school_id: uuid.UUID, user_id: uuid.UUID) -> Any:
    """The person, only if they are one of this school's admins (else 404)."""
    return found(
        db.execute(
            text(f"{ADMIN_SELECT} and u.id = :u"),
            {"s": school_id, "u": user_id},
        ).first()
    )


def end_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(text("delete from user_sessions where user_id = :id"), {"id": user_id})


def list_admins(
    school_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> list[AdminRow]:
    school_row(db, school_id)
    rows = db.execute(
        text(f"{ADMIN_SELECT} order by m.is_primary desc, u.full_name"),
        {"s": school_id},
    )
    return [
        AdminRow(
            id=str(r.id),
            full_name=r.full_name,
            username=r.username,
            email=r.email,
            is_primary=r.is_primary,
            is_active=r.is_active,
            activated=r.activated,
            membership_status=r.membership_status,
        )
        for r in rows
    ]


def resend_activation(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> Detail:
    admin = admin_of(db, school_id, user_id)
    if admin.activated:
        raise ProblemError(409, "This account is already activated.", code="already_activated")
    if admin.email is None:
        raise ProblemError(409, "This account has no email.", code="no_email")
    queue_email(
        db, school_id, "activation", admin.email, activation_data(admin, school_row(db, school_id))
    )
    audit(db, school_id, "school_admins.resend_activation", target=("users", user_id))
    return Detail(detail="Activation email queued.")


def change_admin_email(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    body: NewEmail,
    _: Principal,
    db: Session,
) -> AdminRow:
    admin = admin_of(db, school_id, user_id)
    if body.email != admin.email:
        if db.scalar(text("select platform_email_taken(:e)"), {"e": body.email}):
            raise ProblemError(409, "This email is already used.", code="email_taken")
        # Verified again when the person uses a link sent to it.
        db.execute(
            text("update users set email = :e, email_verified_at = null where id = :id"),
            {"e": body.email, "id": user_id},
        )
        audit(
            db,
            school_id,
            "school_admins.email_change",
            target=("users", user_id),
            old={"email": admin.email},
            new={"email": body.email},
        )
    admin = admin_of(db, school_id, user_id)
    return AdminRow(
        id=str(admin.id),
        full_name=admin.full_name,
        username=admin.username,
        email=admin.email,
        is_primary=admin.is_primary,
        is_active=admin.is_active,
        activated=admin.activated,
        membership_status=admin.membership_status,
    )


def send_reset_link(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ResetLink,
    _: Principal,
    db: Session,
) -> Detail:
    admin = admin_of(db, school_id, user_id)
    if admin.email is None:
        raise ProblemError(409, "This account has no email.", code="no_email")
    queue_email(
        db,
        school_id,
        "password_reset",
        admin.email,
        {"user_id": str(admin.id), "full_name": admin.full_name},
    )
    if body.sign_out_all:
        end_sessions(db, user_id)
    audit(
        db,
        school_id,
        "school_admins.reset_link",
        target=("users", user_id),
        new={"sign_out_all": body.sign_out_all},
    )
    return Detail(detail="Reset link queued.")


def temporary_password(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> TemporaryPassword:
    admin_of(db, school_id, user_id)
    password = issue_temporary_password(db, user_id)
    # The audit records that it happened, never the password (F03 rule 7).
    audit(
        db,
        school_id,
        "school_admins.temporary_password",
        target=("users", user_id),
        new={"must_change_password": True},
    )
    return TemporaryPassword(temporary_password=password)


def sign_out_all(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> None:
    admin_of(db, school_id, user_id)
    end_sessions(db, user_id)
    audit(db, school_id, "school_admins.sign_out_all", target=("users", user_id))


def deactivate(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> None:
    admin_of(db, school_id, user_id)
    db.execute(text("update users set is_active = false where id = :id"), {"id": user_id})
    end_sessions(db, user_id)
    audit(
        db,
        school_id,
        "school_admins.deactivate",
        target=("users", user_id),
        old={"is_active": True},
        new={"is_active": False},
    )


def reactivate_admin(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> None:
    admin_of(db, school_id, user_id)
    db.execute(text("update users set is_active = true where id = :id"), {"id": user_id})
    audit(
        db,
        school_id,
        "school_admins.reactivate",
        target=("users", user_id),
        old={"is_active": False},
        new={"is_active": True},
    )


def make_primary(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Principal,
    db: Session,
) -> None:
    admin = admin_of(db, school_id, user_id)
    if admin.is_primary:
        return
    previous = db.scalar(
        text("select user_id from school_memberships where school_id = :s and is_primary"),
        {"s": school_id},
    )
    # One principal per school (a unique index): clear the old one first.
    db.execute(
        text(
            "update school_memberships set is_primary = false where school_id = :s and is_primary"
        ),
        {"s": school_id},
    )
    db.execute(
        text(
            "update school_memberships set is_primary = true where school_id = :s and user_id = :u"
        ),
        {"s": school_id, "u": user_id},
    )
    audit(
        db,
        school_id,
        "school_admins.make_primary",
        target=("users", user_id),
        old={"principal": str(previous) if previous else None},
        new={"principal": str(user_id)},
    )


def get_settings_page(
    _: Principal,
    db: Session,
) -> settings_model.PlatformSettings:
    return settings_model.load(db)


def change_settings(
    body: dict[str, Any],
    principal: Principal,
    db: Session,
) -> settings_model.PlatformSettings:
    current = settings_model.load(db)
    try:
        wanted = settings_model.merged(current, body)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    before, after = settings_model.flatten(current), settings_model.flatten(wanted)
    changed = {key: value for key, value in after.items() if before[key] != value}
    for key, value in changed.items():
        db.execute(
            text(
                "insert into platform_settings (key, value, updated_by)"
                " values (:k, cast(:v as jsonb), :by)"
                " on conflict (key) do update set value = excluded.value,"
                " updated_by = excluded.updated_by, updated_at = now()"
            ),
            {"k": key, "v": json.dumps(value), "by": principal.user_id},
        )
    if changed:
        audit(
            db,
            None,
            "platform_settings.update",
            old={key: before[key] for key in changed},
            new=changed,
        )
    return wanted


def audit_log(
    _: Principal,
    db: Session,
    school_id: uuid.UUID | None = None,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
    limit: Limit = 50,
    offset: int = 0,
) -> list[AuditRow]:
    return audit_rows(
        db.execute(
            text(
                f"{AUDIT_SELECT}"
                " where (cast(:school as uuid) is null or a.school_id = :school)"
                " and (cast(:action as text) is null or a.action = :action)"
                " and (cast(:actor as uuid) is null or a.actor_id = :actor)"
                " order by a.created_at desc, a.id limit :limit offset :offset"
            ),
            {
                "school": school_id,
                "action": action,
                "actor": actor_id,
                "limit": limit,
                "offset": offset,
            },
        )
    )


def email_log(
    _: Principal,
    db: Session,
    school_id: uuid.UUID | None = None,
    type: str | None = None,
    limit: Limit = 50,
    offset: int = 0,
) -> list[EmailRow]:
    rows = db.execute(
        text(
            "select id, school_id, type, to_address, status, attempts, last_error, created_at,"
            " sent_at from email_outbox"
            " where (cast(:school as uuid) is null or school_id = :school)"
            " and (cast(:type as text) is null or type = :type)"
            " order by created_at desc, id limit :limit offset :offset"
        ),
        {"school": school_id, "type": type, "limit": limit, "offset": offset},
    )
    return [
        EmailRow(
            id=str(r.id),
            school_id=str(r.school_id) if r.school_id else None,
            type=r.type,
            to_address=r.to_address,
            status=r.status,
            attempts=r.attempts,
            last_error=r.last_error,
            created_at=r.created_at,
            sent_at=r.sent_at,
        )
        for r in rows
    ]


def payments(
    _: Principal,
    db: Session,
    school_id: uuid.UUID | None = None,
    limit: Limit = 50,
    offset: int = 0,
) -> list[PaymentRow]:
    rows = db.execute(
        text(
            "select id, school_id, invoice_id, reference, amount_kobo, status, receipt_number,"
            " created_at from payments"
            " where (cast(:school as uuid) is null or school_id = :school)"
            " order by created_at desc, id limit :limit offset :offset"
        ),
        {"school": school_id, "limit": limit, "offset": offset},
    )
    return [
        PaymentRow(
            id=str(r.id),
            school_id=str(r.school_id),
            invoice_id=str(r.invoice_id),
            reference=r.reference,
            amount_kobo=r.amount_kobo,
            status=r.status,
            receipt_number=r.receipt_number,
            created_at=r.created_at,
        )
        for r in rows
    ]
