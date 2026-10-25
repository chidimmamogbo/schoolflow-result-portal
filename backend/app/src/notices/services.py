"""The notice board (BUILD_PROMPT 9.2o; SPEC F17; AC17.1 to AC17.3; D-084 to D-086, D-175).

School admins (`notices.post`) post plain-text notices (D-086) to everyone,
to chosen roles, to chosen classes, or to roles within classes. A class
means its current pupils (those with a login), their parents, the class's
teachers and assistants, and the reviewers whose scope covers it; "school
admin" always means every school admin. The people told are worked out when
the notice is posted and kept in `notice_recipients` (D-084), so the record
says honestly who was told; a pinned notice for everyone also reaches people
who join later. Only active members of the school are told.

Everyone (`notices.read`) reads the published notices addressed to them,
pinned first and then newest, each with a read mark. A parent may belong to
several schools (D-138): their board gathers every school where their link
is active and the Notice board is on, each notice labelled with its school
(AC17.3), with one unread count; the database is switched to each of those
schools in turn, only ever to schools the signed-in person belongs to.

Admins edit a manual notice's title, text and pin; a system notice (from
publishing results or a paid invoice) can only be pinned or archived, its
text never changes. Archiving is final. Every post, edit and archive is
audited. The admins' own list shows every notice with how many people it
reached and how many read it.
"""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.db.session import use_context
from app.src.audit.services import write_audit
from app.src.notices.schemas import (
    Board,
    EditNotice,
    NewNotice,
    Notice,
    SchoolNotice,
    SchoolNotices,
    Unread,
)

CURRENT_SESSION = """(
    not exists (select 1 from terms where is_active)
    or e.session_id = (select session_id from terms where is_active)
)"""

# Everyone a class reaches, with the role each person counts as.
CLASS_PEOPLE = """
    select p.user_id, 'student' as kind from enrolments e
      join students p on p.id = e.student_id join class_arms a on a.id = e.arm_id
     where a.class_id = any(:classes) and e.left_on is null and p.user_id is not null
       and CURRENT_SESSION_RULE
    union
    select g.user_id, 'parent' from enrolments e
      join class_arms a on a.id = e.arm_id
      join guardian_students gs on gs.student_id = e.student_id
      join guardians g on g.id = gs.guardian_id
     where a.class_id = any(:classes) and e.left_on is null and g.user_id is not null
       and CURRENT_SESSION_RULE
    union
    select ta.teacher_id, 'teacher' from teacher_assignments ta
      join class_arms a on a.id = ta.arm_id where a.class_id = any(:classes)
    union
    select ca.assistant_id, 'teacher' from class_assistants ca
      join class_arms a on a.id = ca.arm_id where a.class_id = any(:classes)
    union
    select rs.reviewer_id, 'reviewer' from reviewer_scopes rs
     where rs.class_id = any(:classes)
        or rs.subject_id in (select x.subject_id from arm_subjects x
                             join class_arms a on a.id = x.arm_id where a.class_id = any(:classes))
        or rs.department_id in (select s.department_id from arm_subjects x
                                join class_arms a on a.id = x.arm_id
                                join subjects s on s.id = x.subject_id
                                where a.class_id = any(:classes))
""".replace("CURRENT_SESSION_RULE", CURRENT_SESSION)

# A notice addressed to :me (told when posted, or pinned for everyone).
ADDRESSED = """
    n.status = 'published'
    and (exists (select 1 from notice_recipients r where r.notice_id = n.id and r.user_id = :me)
         or (n.pinned and exists (select 1 from notice_audiences au where au.notice_id = n.id
                                  and au.role is null and au.class_id is null)))
"""


# --- who is told --------------------------------------------------------------------------------


def members(session: Session, roles: list[str] | None = None) -> set[uuid.UUID]:
    rows = session.scalars(
        text(
            "select user_id from school_memberships where status = 'active'"
            " and (cast(:roles as text[]) is null or role = any(:roles))"
        ),
        {"roles": roles},
    )
    return set(rows)


def recipients_for(session: Session, body: NewNotice) -> set[uuid.UUID]:
    audience = body.audience
    if audience.everyone:
        return members(session)
    if not audience.class_ids:
        return members(session, list(audience.roles))
    people = list(session.execute(text(CLASS_PEOPLE), {"classes": audience.class_ids}))
    wanted = set(audience.roles)
    told = {p.user_id for p in people if not wanted or p.kind in wanted}
    if "school_admin" in wanted:
        told |= members(session, ["school_admin"])
    return told & members(session)


def audience_rows(body: NewNotice) -> list[tuple[str | None, uuid.UUID | None]]:
    audience = body.audience
    if audience.everyone:
        return [(None, None)]
    roles: list[str | None] = list(audience.roles) or [None]
    classes: list[uuid.UUID | None] = list(audience.class_ids) or [None]
    return [(role, class_id) for role in roles for class_id in classes]


# --- posting and managing -----------------------------------------------------------------------


def post_notice(session: Session, who: Principal, body: NewNotice) -> SchoolNotice:
    audience = body.audience
    if audience.everyone == bool(audience.roles or audience.class_ids):
        raise ProblemError(422, "Choose everyone, or roles and classes.", code="no_audience")
    for class_id in dict.fromkeys(audience.class_ids):
        found(session.scalar(text("select id from classes where id = :c"), {"c": class_id}))
    notice_id = session.scalar(
        text(
            "insert into notices (school_id, title, body, kind, pinned)"
            " values (:s, :t, :b, 'manual', :p) returning id"
        ),
        {"s": who.school_id, "t": body.title, "b": body.body, "p": body.pinned},
    )
    for role, class_id in audience_rows(body):
        session.execute(
            text(
                "insert into notice_audiences (school_id, notice_id, role, class_id)"
                " values (:s, :n, :r, :c)"
            ),
            {"s": who.school_id, "n": notice_id, "r": role, "c": class_id},
        )
    told = recipients_for(session, body)
    for user_id in told:
        session.execute(
            text(
                "insert into notice_recipients (school_id, notice_id, user_id) values (:s, :n, :u)"
            ),
            {"s": who.school_id, "n": notice_id, "u": user_id},
        )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "notices.post",
        target=("notices", notice_id),
        new={
            "title": body.title,
            "pinned": body.pinned,
            "everyone": audience.everyone,
            "roles": list(audience.roles),
            "class_ids": [str(c) for c in audience.class_ids],
            "recipients": len(told),
        },
    )
    return school_notice(session, notice_id)


def school_notice(session: Session, notice_id: uuid.UUID) -> SchoolNotice:
    row = found(
        session.execute(
            text(f"{ADMIN_SELECT} where n.id = :id"),
            {"id": notice_id},
        ).first()
    )
    return as_school_notice(row)


ADMIN_SELECT = """
    select n.id, n.title, n.body, n.kind, n.pinned, n.status, n.created_at, n.updated_at,
           u.full_name as author,
           (select count(*) from notice_recipients r where r.notice_id = n.id) as recipients,
           (select count(*) from notice_reads r where r.notice_id = n.id) as reads
      from notices n left join users u on u.id = n.author_id
"""


def as_school_notice(r: Any) -> SchoolNotice:
    return SchoolNotice(
        id=str(r.id),
        title=r.title,
        body=r.body,
        kind=r.kind,
        pinned=r.pinned,
        status=r.status,
        author=r.author,
        recipients=r.recipients,
        reads=r.reads,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def list_school_notices(session: Session) -> SchoolNotices:
    rows = session.execute(text(f"{ADMIN_SELECT} order by n.created_at desc, n.id"))
    return SchoolNotices(notices=[as_school_notice(r) for r in rows])


def load(session: Session, notice_id: uuid.UUID) -> Any:
    return found(
        session.execute(
            text("select id, title, body, kind, pinned, status from notices where id = :id"),
            {"id": notice_id},
        ).first()
    )


def edit_notice(
    session: Session, who: Principal, notice_id: uuid.UUID, body: EditNotice
) -> SchoolNotice:
    notice = load(session, notice_id)
    if notice.status != "published":
        raise ProblemError(409, "An archived notice cannot change.", code="wrong_status")
    changes = body.model_dump(exclude_none=True)
    if notice.kind == "system" and ({"title", "body"} & set(changes)):
        raise ProblemError(
            409, "An automatic notice keeps its words; it can be pinned or archived.",
            code="system_notice",
        )  # fmt: skip
    if changes:
        session.execute(
            text(
                "update notices set title = coalesce(:t, title), body = coalesce(:b, body),"
                " pinned = coalesce(:p, pinned) where id = :id"
            ),
            {"t": body.title, "b": body.body, "p": body.pinned, "id": notice.id},
        )
        write_audit(
            session,
            who.school_id,
            who.role.value,
            "notices.edit",
            target=("notices", notice.id),
            old={k: getattr(notice, k) for k in changes},
            new=changes,
        )
    return school_notice(session, notice.id)


def archive_notice(session: Session, who: Principal, notice_id: uuid.UUID) -> SchoolNotice:
    notice = load(session, notice_id)
    if notice.status != "published":
        raise ProblemError(409, "This notice is already archived.", code="wrong_status")
    session.execute(
        text("update notices set status = 'archived' where id = :id"), {"id": notice.id}
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "notices.archive",
        target=("notices", notice.id),
        old={"status": "published"},
        new={"status": "archived"},
    )
    return school_notice(session, notice.id)


# --- reading ------------------------------------------------------------------------------------


def reading_schools(who: Principal) -> list[uuid.UUID]:
    return list(dict.fromkeys(m.school_id for m in who.memberships if m.active))


def board_here(session: Session, who: Principal) -> list[Any]:
    """This school's notices for :me, if its Notice board is on."""
    school = session.execute(
        text(
            "select s.id, s.name, s.code, (select enabled from school_features"
            "  where feature = 'notice_board') as board from schools s"
            " where s.id = current_setting('app.school_id')::uuid and s.status = 'active'"
        )
    ).first()
    if school is None or not school.board:
        return []
    rows = session.execute(
        text(
            "select n.id, n.title, n.body, n.kind, n.pinned, n.created_at,"  # noqa: S608
            " exists (select 1 from notice_reads r where r.notice_id = n.id"
            "  and r.user_id = :me) as read"
            f" from notices n where {ADDRESSED}"
        ),
        {"me": who.user_id},
    )
    return [(school, r) for r in rows]


def each_school[T](session: Session, who: Principal, work: Callable[[], list[T]]) -> list[T]:
    """Run `work` in every school the signed-in person belongs to, then put their school back."""
    results: list[T] = []
    try:
        for school_id in reading_schools(who):
            use_context(session, school_id=school_id, user_id=who.user_id)
            results.extend(work())
    finally:
        use_context(session, school_id=who.school_id, user_id=who.user_id)
    return results


def board(session: Session, who: Principal) -> Board:
    found_notices: list[tuple[Any, Any]] = each_school(
        session, who, lambda: board_here(session, who)
    )
    notices = [
        Notice(
            id=str(r.id),
            school_id=str(school.id),
            school_name=school.name,
            school_code=school.code,
            title=r.title,
            body=r.body,
            kind=r.kind,
            pinned=r.pinned,
            read=r.read,
            created_at=r.created_at,
        )
        for school, r in found_notices
    ]
    notices.sort(key=lambda n: (not n.pinned, -n.created_at.timestamp(), n.id))
    return Board(notices=notices)


def unread(session: Session, who: Principal) -> Unread:
    found_notices: list[tuple[Any, Any]] = each_school(
        session, who, lambda: board_here(session, who)
    )
    return Unread(unread=sum(1 for _, r in found_notices if not r.read))


def mark_read(session: Session, who: Principal, notice_id: uuid.UUID) -> None:
    """Find the notice among the person's schools, then record the read once."""

    def here() -> list[uuid.UUID]:
        mine = [r for _, r in board_here(session, who) if r.id == notice_id]
        if mine:
            session.execute(
                text(
                    "insert into notice_reads (school_id, notice_id, user_id)"
                    " values (current_setting('app.school_id')::uuid, :n, :me)"
                    " on conflict (notice_id, user_id) do nothing"
                ),
                {"n": notice_id, "me": who.user_id},
            )
        return [notice_id] if mine else []

    if not each_school(session, who, here):
        raise ProblemError(404, "Not Found")
