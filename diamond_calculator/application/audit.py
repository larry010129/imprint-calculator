"""Audit trail for admin actions (status changes, deletes, password resets).

Writes structured lines through the standard logging module (logger name
'diamond_calculator.audit') so they land wherever the app's other logs go
(stdout under systemd/journald, or a file if LOG_FILE is configured) without
needing a separate database table.
"""
import logging

from flask import request
from flask_login import current_user

log = logging.getLogger('diamond_calculator.audit')


def log_admin_action(action, **fields):
    actor = getattr(current_user, 'username', 'unknown') if current_user else 'unknown'
    ip = request.remote_addr if request else 'n/a'
    detail = ' '.join(f'{key}={value!r}' for key, value in fields.items())
    log.info('action=%s actor=%s ip=%s %s', action, actor, ip, detail)
