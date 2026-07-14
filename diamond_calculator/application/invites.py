"""Registration invite code validation."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from diamond_calculator.repository.models import InviteCode, db


def invite_required() -> bool:
    if os.environ.get('REQUIRE_INVITE_CODE', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    return bool((os.environ.get('REGISTRATION_INVITE_CODE') or '').strip())


def validate_invite_code(code: str) -> str | None:
    """Return error message if invalid, else None."""
    if not invite_required():
        return None

    code = (code or '').strip()
    if not code:
        return '請輸入邀請碼。 (Invite code is required.)'

    env_code = (os.environ.get('REGISTRATION_INVITE_CODE') or '').strip()
    if env_code and secrets.compare_digest(code, env_code):
        return None

    invite = InviteCode.query.filter_by(code=code).first()
    if invite is None:
        return '邀請碼無效或已過期。 (Invalid or expired invite code.)'
    if not invite.is_active:
        return '邀請碼無效或已過期。 (Invalid or expired invite code.)'
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        return '邀請碼無效或已過期。 (Invalid or expired invite code.)'
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return '邀請碼已達使用上限。 (Invite code has reached its use limit.)'
    return None


def consume_invite_code(code: str, user_id: int) -> None:
    """Mark a DB-backed invite code as used (env codes are not consumed)."""
    code = (code or '').strip()
    env_code = (os.environ.get('REGISTRATION_INVITE_CODE') or '').strip()
    if env_code and secrets.compare_digest(code, env_code):
        return

    invite = InviteCode.query.filter_by(code=code).first()
    if invite is None:
        return
    invite.use_count = (invite.use_count or 0) + 1
    invite.used_by_id = user_id
    invite.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        invite.is_active = False


def role_for_invite_code(code: str) -> str:
    """Role to assign on registration. Env invites never grant admin."""
    code = (code or '').strip()
    if not code:
        return 'provider'
    env_code = (os.environ.get('REGISTRATION_INVITE_CODE') or '').strip()
    if env_code and secrets.compare_digest(code, env_code):
        return 'provider'
    invite = InviteCode.query.filter_by(code=code).first()
    if invite is not None and bool(getattr(invite, 'grants_admin', False)):
        return 'admin'
    return 'provider'


def generate_invite_code() -> str:
    return secrets.token_urlsafe(9)[:12].upper()
