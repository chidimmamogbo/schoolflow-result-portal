"""Migration 25: verification names the newer revision (CHANGE 2026-10-24; D-074, D-172).

SPEC F13; the VerifyAfter design: "A newer version exists (revision 2,
10 Dec 2026)".

verify_report() (migration 15) said only whether a newer revision exists.
It now also returns that newest revision's number and publication date, so
the SUPERSEDED page can name them. It still never returns the newer
revision's code, the student's full name or any score. A function's return
columns cannot be changed in place, so it is dropped and created again,
with the same owner-run settings and the same single grant to app_verifier.
No table changes.

Revision ID: a4d9e2c71b05
Revises: 8c1f4d2b6e93
Create Date: 2026-10-24 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d9e2c71b05"
down_revision: str | Sequence[str] | None = "8c1f4d2b6e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEAD = """
create function verify_report(code text)
returns table (
    school_name text,
    masked_name text,
    session_name text,
    term_number smallint,
    status text,
    revision smallint,
    report_code text,
    published_at timestamptz,
    has_newer_revision boolean{extra}
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
    cleaned text;
begin
    -- D-072: forgiving input; capitals, spaces and dashes do not matter.
    cleaned := upper(regexp_replace(coalesce(code, ''), '[^0-9A-Za-z]', '', 'g'));
    if char_length(cleaned) <> 12 then
        return;
    end if;

    return query
    select s.name, d.masked_name, a.name, t.term_number, d.status, d.revision, d.report_code,
           d.published_at,
           exists (
               select 1
                 from public.report_documents newer
                where newer.enrolment_id = d.enrolment_id
                  and newer.term_id = d.term_id
                  and newer.revision > d.revision
           ){select_extra}
      from public.verification_tokens v
      join public.report_documents d on d.id = v.report_document_id
      join public.schools s on s.id = d.school_id
      join public.terms t on t.id = d.term_id
      join public.academic_sessions a on a.id = t.session_id{join_extra}
     where v.code_hash = sha256(convert_to(
               substr(cleaned, 1, 4) || '-' || substr(cleaned, 5, 4) || '-'
               || substr(cleaned, 9, 4), 'UTF8'));
end
$$;

revoke all on function verify_report(text) from public;
grant execute on function verify_report(text) to app_verifier;
"""

NEW = HEAD.format(
    extra=",\n    newer_revision smallint,\n    newer_published_at timestamptz",
    select_extra=",\n           latest.revision, latest.published_at",
    join_extra="""
      left join lateral (
           select n.revision, n.published_at
             from public.report_documents n
            where n.enrolment_id = d.enrolment_id
              and n.term_id = d.term_id
              and n.revision > d.revision
            order by n.revision desc
            limit 1
      ) latest on true""",
)
OLD = HEAD.format(extra="", select_extra="", join_extra="")


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): one function, no tables.
    op.execute("drop function verify_report(text)")
    op.execute(NEW)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop function verify_report(text)")
    op.execute(OLD)
