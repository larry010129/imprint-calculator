import time

from flask import request

_login_attempts = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

_register_attempts = {}
REGISTER_MAX_ATTEMPTS = 10
REGISTER_LOCKOUT_SECONDS = 600


def _lockout_key(username):
    return (username, _client_ip())


def is_locked_out(username):
    entry = _login_attempts.get(_lockout_key(username))
    if not entry:
        return False
    fail_count, locked_until = entry
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() < locked_until:
        return True
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() >= locked_until:
        _login_attempts.pop(_lockout_key(username), None)
    return False


def record_login_failure(username):
    key = _lockout_key(username)
    fail_count, _ = _login_attempts.get(key, (0, 0))
    fail_count += 1
    locked_until = time.time() + LOGIN_LOCKOUT_SECONDS if fail_count >= LOGIN_MAX_ATTEMPTS else 0
    _login_attempts[key] = (fail_count, locked_until)


def record_login_success(username):
    _login_attempts.pop(_lockout_key(username), None)


def clear_login_lockout(username):
    """Admin helper — clear lockout for a username across all IPs."""
    keys = [k for k in _login_attempts if k[0] == username]
    for key in keys:
        _login_attempts.pop(key, None)


def _client_ip():
    # request.remote_addr is trustworthy here because create_app() wraps the
    # WSGI app in ProxyFix, which already resolves X-Forwarded-For for exactly
    # the configured number of trusted proxy hops. Do not re-parse the raw
    # header here - that would let a client spoof its own IP.
    return request.remote_addr or 'unknown'


def is_register_locked_out():
    entry = _register_attempts.get(_client_ip())
    if not entry:
        return False
    fail_count, locked_until = entry
    if fail_count >= REGISTER_MAX_ATTEMPTS and time.time() < locked_until:
        return True
    if fail_count >= REGISTER_MAX_ATTEMPTS and time.time() >= locked_until:
        _register_attempts.pop(_client_ip(), None)
    return False


def record_register_failure():
    ip = _client_ip()
    fail_count, _ = _register_attempts.get(ip, (0, 0))
    fail_count += 1
    locked_until = time.time() + REGISTER_LOCKOUT_SECONDS if fail_count >= REGISTER_MAX_ATTEMPTS else 0
    _register_attempts[ip] = (fail_count, locked_until)


def record_register_success():
    _register_attempts.pop(_client_ip(), None)
