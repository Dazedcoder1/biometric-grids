"""
A person's name and employee ID are fixed once their account exists.

Enforced at the model layer, on every flush, so no route — present or future,
for any role, Super Admin included — can rename someone or change their
employee ID. A route that tries gets IdentityLocked, which main.py turns into
a 400 with a plain message. The routes that used to allow it now refuse
before getting this far; this is the backstop.

Allowed: filling a value that was never set (an old account created without
an employee ID can still be given one, once). Setting the same value again is
not a change and passes.
"""

from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

LOCKED_FIELDS = ("name", "employee_code")
MESSAGE = "A person's name and employee ID can't be changed after their account is created."


class IdentityLocked(Exception):
    def __init__(self, field: str):
        self.field = field
        super().__init__(MESSAGE)


def changed_locked_field(obj) -> str | None:
    """The first locked field this pending change would alter, or None."""
    state = inspect(obj)
    if not state.persistent:
        return None                       # still being created
    for field in LOCKED_FIELDS:
        hist = state.attrs[field].history
        if not hist.has_changes():
            continue
        before = hist.deleted[0] if hist.deleted else None
        after = hist.added[0] if hist.added else None
        if before not in (None, "") and before != after:
            return field
    return None


def install() -> None:
    from app.models.domain import User

    @event.listens_for(Session, "before_flush")
    def _identity_is_permanent(session, flush_context, instances):
        for obj in session.dirty:
            if isinstance(obj, User):
                field = changed_locked_field(obj)
                if field:
                    raise IdentityLocked(field)
