"""Nobody sees the actions of someone more senior — core/audit_visibility."""

from types import SimpleNamespace as U

import pytest

from app.core import audit_visibility as V

EMP = U(id=1, role="employee")
DEPT = U(id=2, role="org_admin")          # Department Admin
ORG = U(id=3, role="tenant_admin")        # Organisation Admin
SUPER = U(id=4, role="super_admin")


@pytest.mark.parametrize("viewer,actor_role,visible", [
    (EMP, "employee", True), (EMP, "org_admin", False), (EMP, "tenant_admin", False), (EMP, "super_admin", False),
    (DEPT, "employee", True), (DEPT, "org_admin", True), (DEPT, "tenant_admin", False), (DEPT, "super_admin", False),
    (ORG, "employee", True), (ORG, "org_admin", True), (ORG, "tenant_admin", True), (ORG, "super_admin", False),
    (SUPER, "super_admin", True), (SUPER, "tenant_admin", True),
    # API-key sign-in is an Organisation Admin's action.
    (DEPT, "api_key", False), (ORG, "api_key", True),
    # No person behind it: visible to anyone who can see the log.
    (EMP, None, True), (DEPT, "system", True), (DEPT, "unknown", True),
])
def test_can_see(viewer, actor_role, visible):
    assert V.can_see(viewer, actor_role, actor_id=99) is visible


def test_own_actions_always_visible():
    # e.g. something a Department Admin did back when they were recorded at a higher level
    assert V.can_see(DEPT, "tenant_admin", actor_id=DEPT.id) is True


def test_grants_all_sees_everything():
    custom = U(id=9, role="employee")
    assert V.can_see(custom, "super_admin", actor_id=1, grants_all=True) is True
    assert V.hidden_roles(V.viewer_rank(custom, grants_all=True)) == []


def test_hidden_roles():
    assert V.hidden_roles(V.viewer_rank(SUPER)) == []
    assert V.hidden_roles(V.viewer_rank(ORG)) == ["super_admin"]
    assert V.hidden_roles(V.viewer_rank(DEPT)) == ["api_key", "super_admin", "tenant_admin"]
    assert V.hidden_roles(V.viewer_rank(EMP)) == ["api_key", "org_admin", "super_admin", "tenant_admin"]


def test_actor_condition_none_for_super_admin():
    from app.models.security import AuditLog
    assert V.actor_condition(AuditLog.actor_role, AuditLog.actor_id, SUPER) is None
    assert V.actor_condition(AuditLog.actor_role, AuditLog.actor_id, ORG) is not None
