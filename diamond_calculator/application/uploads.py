"""Validated image upload/storage for admin-managed product photos.

Every uploaded file is re-encoded through Pillow before being written to
disk: this strips EXIF metadata, verifies the payload is really a decodable
image (not just a file with a spoofed extension), normalizes the output
format, and caps the max dimension — so admins can drop in phone photos of
any size/orientation without bloating storage or leaking location data.
"""
from __future__ import annotations

import io
import shutil
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = ROOT / 'static' / 'uploads' / 'products'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB cap per image
MAX_DIMENSION = 1600  # px, longest side after normalization
OUTPUT_FORMAT = 'PNG'
OUTPUT_EXT = 'png'


class UploadError(ValueError):
    """Raised when an uploaded file fails validation."""


def _has_allowed_extension(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image_file(file_storage) -> bytes:
    """Reads + validates an uploaded FileStorage. Returns raw bytes.

    Raises UploadError with a user-facing message on any problem.
    """
    if file_storage is None or not file_storage.filename:
        raise UploadError('請選擇要上傳的圖片。 (Please choose an image to upload.)')

    filename = secure_filename(file_storage.filename)
    if not filename or not _has_allowed_extension(filename):
        raise UploadError('圖片格式僅支援 PNG / JPG / JPEG / WEBP。 (Only PNG/JPG/JPEG/WEBP images are supported.)')

    data = file_storage.read()
    if not data:
        raise UploadError('圖片檔案是空的。 (The uploaded file is empty.)')
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError('圖片檔案過大，請上傳 5MB 以內的圖片。 (Image is too large; max size is 5MB.)')

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError):
        raise UploadError('無法辨識的圖片檔案，請確認檔案未損毀。 (Could not read this image file.)')

    return data


def _normalize_image(data: bytes) -> bytes:
    """Re-encodes image bytes: strips EXIF, flattens transparency-safe RGBA/RGB,
    caps the longest side at MAX_DIMENSION, and outputs as PNG."""
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert('RGBA') if img.mode in ('RGBA', 'LA') or 'transparency' in img.info else img.convert('RGB')
        width, height = img.size
        longest = max(width, height)
        if longest > MAX_DIMENSION:
            scale = MAX_DIMENSION / longest
            img = img.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format=OUTPUT_FORMAT)
        return out.getvalue()


def save_product_image(product_id: int, color: str, file_storage) -> str:
    """Validates + saves an uploaded product photo.

    Returns the file path relative to static/ (e.g.
    'uploads/products/12/white_a1b2c3d4.png') suitable for ProductImage.file_path.
    """
    raw = validate_image_file(file_storage)
    normalized = _normalize_image(raw)

    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)

    # Unique suffix avoids stale browser/CDN caches showing an old photo
    # after an admin replaces one for the same color.
    token = uuid.uuid4().hex[:8]
    out_name = f'{color}_{token}.{OUTPUT_EXT}'
    out_path = product_dir / out_name
    out_path.write_bytes(normalized)

    return f'uploads/products/{product_id}/{out_name}'


def delete_product_image(file_path: str) -> None:
    """Best-effort delete of a previously-saved upload (ignores missing files)."""
    if not file_path or not file_path.startswith('uploads/products/'):
        return
    full = ROOT / 'static' / file_path
    try:
        full.unlink(missing_ok=True)
    except OSError:
        pass


def copy_product_image(file_path: str, product_id: int, color: str) -> str:
    """Copy a normalized product image into another product's folder."""
    if not file_path or not file_path.startswith('uploads/products/'):
        raise UploadError('無法複製商品圖片。')
    source = ROOT / 'static' / file_path
    if not source.is_file():
        raise UploadError('原商品圖片不存在，無法複製。')

    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    out_name = f'{color}_{uuid.uuid4().hex[:8]}.{OUTPUT_EXT}'
    out_path = product_dir / out_name
    shutil.copy2(source, out_path)
    return f'uploads/products/{product_id}/{out_name}'
