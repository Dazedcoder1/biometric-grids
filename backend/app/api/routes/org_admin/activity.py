"""
Recent activity in this Org Admin's department.

`orgApi.getActivityLog()` had no route behind it, so the Activity page showed
its error state on every load.

Built from notifications rather than from the credential-vault audit log:
this screen answers "what has been happening with my team" — leave requests,
attendance, joiners — not "who touched which secret". Those are different
questions with different sensitivities, and the vault has its own audit viewer
with its own permission.

Like every log, it never shows what someone more senior did: entries whose
actor is a Tenant Admin or Super Admin are left out (core/audit_visibility).
An Org Admin with no department sees only their own notifications, the same
as their audit log, rather than the whole organisation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_role
from app.core import audit_visibility as visibility
from app.db.session import get_db
from app.models.domain import User

router = APIRouter()


@router.get("/activity")
async def department_activity(
    limit: int = Query(50, le=200),
    current_user: User = Depends(require_role("org_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text(
            """
            SELECT n.notification_id AS id,
                   n.event_type,
                   n.title,
                   n.message,
                   n.created_at,
                   n.is_read,
                   n.entity_name,
                   -- actor_name is denormalised onto the row so the record
                   -- survives the actor being deleted; fall back to the live
                   -- user only when the stored copy is missing.
                   COALESCE(n.actor_name, actor.name) AS actor_name
              FROM notifications n
              LEFT JOIN users actor     ON actor.id = n.actor_id
              LEFT JOIN users recipient ON recipient.id = n.recipient_id
             WHERE n.tenant_id = :tenant_id
               -- Department scope via the recipient. With no department, only
               -- what was sent to the Org Admin themselves.
               AND (
                     (CAST(:dept_id AS INTEGER) IS NULL AND n.recipient_id = :me)
                  OR recipient.dept_id = :dept_id
               )
               -- Nothing done by someone more senior. A deleted actor or a
               -- system notification (no actor) stays visible.
               AND (actor.id IS NULL OR actor.id = :me OR actor.role NOT IN :hidden)
             ORDER BY n.created_at DESC
             LIMIT :limit
            """
        ).bindparams(bindparam("hidden", expanding=True)),
        {
            "tenant_id": current_user.tenant_id,
            "dept_id": current_user.dept_id,
            "me": current_user.id,
            "hidden": tuple(visibility.hidden_roles(visibility.viewer_rank(current_user))),
            "limit": limit,
        },
    )
    return result.mappings().all()
