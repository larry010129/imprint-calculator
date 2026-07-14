"""Encode/decode validated shop configurations for public summary URLs."""

import base64
import json

MAX_TOKEN_LENGTH = 4096


def encode_config(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def decode_config(token):
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise ValueError('invalid configuration')
    try:
        padding = '=' * (-len(token) % 4)
        raw = base64.urlsafe_b64decode((token + padding).encode('ascii'))
        data = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid configuration') from exc
    if not isinstance(data, dict):
        raise ValueError('invalid configuration')
    return data
