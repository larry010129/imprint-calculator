"""Per-page module folders: each feature owns templates/ and static/ under ROOT/<module>/."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Flask, url_for
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader

ROOT = Path(__file__).resolve().parent.parent

# Template modules searched by PrefixLoader (module/path.html -> <module>/templates/path.html).
TEMPLATE_MODULES = (
    'layout',
    'macros',
    'admin',
    'shop',
    'auth',
    'gold',
    'orders',
    'cart',
    'favorites',
    'profile',
    'notifications',
    'share',
    'marketing',
    'errors',
)

# Modules that may serve page-local assets at /<module>/static/<path>.
STATIC_MODULES = (
    'admin',
    'shop',
    'auth',
    'marketing',
    'share',
    'orders',
    'cart',
)


def build_template_loader() -> ChoiceLoader:
    mapping = {}
    for name in TEMPLATE_MODULES:
        folder = ROOT / name / 'templates'
        if folder.is_dir():
            mapping[name] = FileSystemLoader(str(folder))
    if not mapping:
        raise RuntimeError('No module template folders found under project root')
    return ChoiceLoader([PrefixLoader(mapping)])


def register_module_static_blueprints(app: Flask) -> None:
    for name in STATIC_MODULES:
        folder = ROOT / name / 'static'
        if not folder.is_dir():
            continue
        bp = Blueprint(
            f'{name}_assets',
            __name__,
            static_folder=str(folder),
            static_url_path=f'/{name}/static',
        )
        app.register_blueprint(bp)


def module_static(module: str, filename: str) -> str:
    """URL for assets in <module>/static/ (e.g. admin/css/admin-dashboard.css)."""
    endpoint = f'{module}_assets.static'
    return url_for(endpoint, filename=filename)


def register_template_globals(app: Flask) -> None:
    app.jinja_env.globals['module_static'] = module_static
