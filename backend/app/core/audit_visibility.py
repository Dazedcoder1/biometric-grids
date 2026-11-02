"""
Whose actions a person may see in any log.

Seniority runs Employee < Department Admin < Organisation Admin < Super Admin.
A viewer sees what was done by people at their own level or below, plus
everything they did themselves — never the actions of someone above them:

    Super Admin          everything
    Organisation Admin   not the Super Admin's actions
    Department Admin     not the Organisation Admin's or the Super Admin's
    Employee (and HR)    not any admin's

Role names are the codes stored on users.role and audit_log.actor_role:
tenant_admin is the Organisation Admin, org_admin the Department Admin. HR is
a flag on top of a role, not a role of its own, so an HR employee is ranked as
an employee.

The level used is the role recorded on the entry when it was written, so an
admin's past actions stay hidden after they are demoted, and an employee's
stay visible after they are promoted.

Entries with no person behind them (system jobs, failed sign-ins by unknown
accounts) are visible to anyone who can see the log at all. A sign-in with the
organisation's API key is an Organisation Admin's action and ranked as one.

This narrows the existing scope rules (organisation, department); it never
widens them.
"""

from __future__ import annotations

from sqlalchemy import or_

RANK: dict[str, int] = {
    "employee": 1,
    "org_admin": 2,         # Department Admin
    "tenant_admin": 3,      # Organisation Admin
    "api_key": 3,           # signed in with the organisation's API key
    "super_admin": 4,
}
TOP = 4


def viewer_rank(user, grants_all: bool = False) -> int:
    if grants_all or getattr(user, "role", None) == "super_admin":
        return TOP
    return RANK.get(getattr(user, "role", None) or "", 1)


def hidden_roles(rank: int) -> list[str]:
    """Actor roles above this rank, whose actions are hidden."""
    return sorted(r for r, n in RANK.items() if n > rank)


def can_see(viewer, actor_role: str | None, actor_id: int | None, grants_all: bool = False) -> bool:
    """The same rule for one entry, in Python."""
    if actor_id is not None and actor_id == getattr(viewer, "id", None):
        return True
    return RANK.get(actor_role or "", 0) <= viewer_rank(viewer, grants_all)


def actor_condition(role_col, id_col, viewer, grants_all: bool = False):
    """
    SQL condition on (actor role, actor id) columns, or None when nothing is
    hidden. Works for audit_log (actor_role, actor_id) and for anything joined
    to users (users.role, users.id).
    """
    hidden = hidden_roles(viewer_rank(viewer, grants_all))
    if not hidden:
        return None
    return or_(role_col.is_(None), role_col.notin_(hidden), id_col == viewer.id)
