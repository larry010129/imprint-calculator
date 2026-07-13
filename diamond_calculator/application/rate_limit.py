"""Shared IP-based rate limiter.

Uses request.remote_addr as the key. This is only trustworthy because
create_app() wraps the WSGI app in ProxyFix, which derives remote_addr from
X-Forwarded-For for exactly the configured number of trusted proxy hops
(TRUSTED_PROXY_COUNT) and ignores any extra, attacker-supplied hops.

Storage defaults to an in-process memory backend, which is fine for a single
Waitress process but resets on restart and is not shared across multiple
processes/machines. Set RATELIMIT_STORAGE_URI (e.g. redis://host:6379) for a
shared backend in a multi-process or multi-instance deployment.
"""
import logging
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

log = logging.getLogger(__name__)

STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

if STORAGE_URI == 'memory://':
    log.warning(
        'Rate limiter is using in-memory storage: login/register limits will '
        'reset on restart and will not be shared across multiple processes. '
        'Set RATELIMIT_STORAGE_URI (e.g. a redis:// URL) for production.'
    )

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=STORAGE_URI,
    default_limits=[],
    headers_enabled=True,
)
