import re

from diamond_calculator.application.diamond_options import (
    DEFAULT_STONE_COUNT_BY_CATEGORY,
    STONE_COUNT_CATEGORIES,
    VALID_DIAMOND_KINDS,
    VALID_DIAMOND_SHAPES,
    VALID_FANCY_COLORS,
    VALID_STONE_COUNTS,
)

VALID_CATEGORIES = {'pendant', 'ring', 'earring', 'bracelet', 'chain'}
CATEGORY_DISPLAY_ORDER = ['pendant', 'ring', 'earring', 'bracelet', 'chain']
VALID_CARATS = {'0.1', '0.2', '0.3', '0.5', '1.0'}
VALID_CARATS_CHAIN = {'3fen', '4fen'}
VALID_TYPES = {'A', 'B', 'C'}
VALID_GOLDS = {'9k', '14k', '18k', 'pt950', 's925'}
GOLD_DISPLAY_ORDER = ('9k', '14k', '18k', 'pt950', 's925')
GOLDS_REQUIRING_COLOR = {'14k', '18k'}
GOLD_WHITE_ONLY = {'9k'}
VALID_COLORS = {'white', 'yellow', 'rose'}
RING_SIZE_MIN, RING_SIZE_MAX = 5, 18
ENGRAVING_MAX_LENGTH = 10
GIRDLE_ENGRAVING_CATEGORIES = {'ring'}
CHAIN_LENGTH_OPTIONS_CM = (35, 40, 45, 50, 55, 60)
BRACELET_LENGTH_OPTIONS_CM = (15, 16, 17, 18, 19, 20, 21)
PAGE_SIZE = 25
ADMIN_PAGE_SIZES = (10, 20, 50)
ADMIN_PAGE_SIZE_DEFAULT = 10

USERNAME_MIN, USERNAME_MAX = 3, 32
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]+$')
PASSWORD_MIN = 8
PASSWORD_MAX = 128


def sort_golds(golds):
    order = {g: i for i, g in enumerate(GOLD_DISPLAY_ORDER)}
    return sorted(golds, key=lambda g: order.get(g, 999))


def validate_username(username):
    """Returns an error message, or None if the username is acceptable."""
    username = (username or '').strip()
    if not username:
        return '帳號為必填欄位。 (Username is required.)'
    if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
        return f'帳號長度需為 {USERNAME_MIN}-{USERNAME_MAX} 個字元。 (Username must be {USERNAME_MIN}-{USERNAME_MAX} characters.)'
    if not USERNAME_RE.match(username):
        return '帳號僅可使用英文字母、數字、點號、底線與連字號。 (Username may only contain letters, numbers, "." "_" "-".)'
    return None


def validate_password(password, username=None):
    """Returns an error message, or None if the password is acceptable."""
    password = password or ''
    if len(password) < PASSWORD_MIN:
        return f'密碼至少需要 {PASSWORD_MIN} 個字元。 (Password must be at least {PASSWORD_MIN} characters.)'
    if len(password) > PASSWORD_MAX:
        return '密碼過長。 (Password is too long.)'
    if not password.strip():
        return '密碼不可只包含空白字元。 (Password cannot be only whitespace.)'
    if username and password.lower() == username.strip().lower():
        return '密碼不可與帳號相同。 (Password cannot be the same as the username.)'
    return None


def validate_submission_fields(data, partial=False):
    errors = []
    cleaned = {}

    def check_choice(key, valid, required=True):
        val = data.get(key)
        if val is None:
            if required and not partial:
                errors.append(f'{key} is required')
        elif str(val) not in valid:
            errors.append(f'invalid {key}')
        else:
            cleaned[key] = str(val)

    check_choice('category', VALID_CATEGORIES)
    check_choice('gold', VALID_GOLDS)

    # 'type' is now a Product id (from the admin-managed catalog), not a
    # fixed A/B/C letter, so it can't be checked against a static set here.
    # Its existence (and category/metal/carat match) is verified downstream
    # by pricing.get_product_variant() when computing the price.
    type_val = data.get('type')
    if type_val is None:
        if not partial:
            errors.append('type is required')
    else:
        cleaned['type'] = str(type_val)

    carat = data.get('carat')
    cat = cleaned.get('category') or str(data.get('category', ''))
    if carat is None:
        if not partial:
            errors.append('carat is required')
    else:
        valid_c = VALID_CARATS_CHAIN if cat == 'chain' else VALID_CARATS
        if str(carat) not in valid_c:
            errors.append('invalid carat')
        else:
            cleaned['carat'] = str(carat)

    color = data.get('color')
    if color is not None and str(color) not in VALID_COLORS:
        errors.append('invalid color')
    elif color is not None:
        cleaned['color'] = str(color)

    if not partial:
        gold = cleaned.get('gold')
        if gold in GOLD_WHITE_ONLY:
            if cleaned.get('color') not in (None, 'white'):
                errors.append('9k only supports white')
            else:
                cleaned['color'] = 'white'
        elif gold in GOLDS_REQUIRING_COLOR and 'color' not in cleaned:
            errors.append('color is required for gold alloys')

    ring_size = data.get('ringSize')
    if ring_size is not None:
        try:
            ring_size = float(ring_size)
        except (TypeError, ValueError):
            ring_size = -1
        if not (RING_SIZE_MIN <= ring_size <= RING_SIZE_MAX):
            errors.append('invalid ringSize')
        else:
            cleaned['ringSize'] = ring_size

    if not partial and cleaned.get('category') == 'ring' and 'ringSize' not in cleaned:
        errors.append('ringSize is required for rings')

    def clean_engraving(key, permitted_categories):
        value = data.get(key)
        if value is None:
            return
        value = ''.join(char for char in str(value).strip() if char.isprintable())
        if cleaned.get('category') not in permitted_categories:
            if value:
                errors.append(f'{key} is not available for this category')
        elif len(value) > ENGRAVING_MAX_LENGTH:
            errors.append(f'{key} must be at most {ENGRAVING_MAX_LENGTH} characters')
        elif value and key == 'engravingGirdle' and not re.fullmatch(r'[A-Za-z0-9]{1,10}', value):
            errors.append(f'{key} must be 1–10 letters or digits')
        elif value:
            cleaned[key] = value

    clean_engraving('engravingBand', {'ring'})
    clean_engraving('engravingGirdle', GIRDLE_ENGRAVING_CATEGORIES)

    def clean_chain_length(key, required=False, allowed=CHAIN_LENGTH_OPTIONS_CM):
        value = data.get(key)
        if value is None:
            if required:
                errors.append(f'{key} is required')
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = -1
        if value not in allowed:
            errors.append(f'invalid {key}')
            return None
        return value

    if cleaned.get('category') == 'chain':
        length = clean_chain_length('lengthCm', required=not partial)
        if length is not None:
            cleaned['lengthCm'] = length

    if cleaned.get('category') == 'bracelet':
        length = clean_chain_length('lengthCm', required=not partial, allowed=BRACELET_LENGTH_OPTIONS_CM)
        if length is not None:
            cleaned['lengthCm'] = length

    include_chain = bool(data.get('includeChain', False))
    cat = cleaned.get('category') or str(data.get('category', ''))
    diamond_kind = data.get('diamondKind', 'white')
    if diamond_kind is not None:
        diamond_kind = str(diamond_kind)
        if diamond_kind not in VALID_DIAMOND_KINDS:
            errors.append('invalid diamondKind')
        else:
            cleaned['diamondKind'] = diamond_kind

    diamond_shape = data.get('diamondShape', 'round')
    if diamond_shape is not None:
        diamond_shape = str(diamond_shape)
        if diamond_shape not in VALID_DIAMOND_SHAPES:
            errors.append('invalid diamondShape')
        else:
            cleaned['diamondShape'] = diamond_shape

    if cat == 'chain':
        cleaned['diamondKind'] = 'white'
        cleaned['diamondShape'] = 'round'
    elif cleaned.get('diamondKind') == 'fancy':
        fancy_color = data.get('fancyColor')
        if fancy_color is None:
            if not partial:
                errors.append('fancyColor is required for fancy diamonds')
        elif str(fancy_color) not in VALID_FANCY_COLORS:
            errors.append('invalid fancyColor')
        else:
            cleaned['fancyColor'] = str(fancy_color)

        carat = cleaned.get('carat')
        if carat and not partial:
            from diamond_calculator.application.diamond_options import is_fancy_carat_allowed
            if not is_fancy_carat_allowed(carat):
                errors.append('fancy diamonds require carat 0.30 or above')

        stone_count = data.get('stoneCount')
        if cat in STONE_COUNT_CATEGORIES:
            if stone_count is None:
                if not partial:
                    cleaned['stoneCount'] = DEFAULT_STONE_COUNT_BY_CATEGORY.get(cat, 2)
            else:
                try:
                    stone_count = int(stone_count)
                except (TypeError, ValueError):
                    stone_count = -1
                if stone_count not in VALID_STONE_COUNTS:
                    errors.append('invalid stoneCount')
                else:
                    cleaned['stoneCount'] = stone_count
    else:
        cleaned.setdefault('diamondKind', 'white')
        cleaned.setdefault('diamondShape', 'round')

    if cat == 'earring':
        cleaned['stoneCount'] = 2
    elif cat == 'bracelet':
        cleaned.pop('stoneCount', None)

    if cat != 'chain' and not partial:
        carat = cleaned.get('carat')
        shape = cleaned.get('diamondShape', 'round')
        if carat and shape != 'round':
            from diamond_calculator.application.diamond_options import is_shape_carat_allowed
            if not is_shape_carat_allowed(carat, shape):
                errors.append('non-round diamond shapes require carat 0.30 or above')

    if cleaned.get('category') == 'pendant':
        cleaned['includeChain'] = include_chain
        if include_chain:
            chain_id = data.get('chainProductId')
            chain_gold = data.get('chainGold')
            chain_color = data.get('chainColor')
            if not chain_id:
                if not partial:
                    errors.append('chainProductId is required')
            else:
                cleaned['chainProductId'] = str(chain_id)
            if chain_gold is None or str(chain_gold) == '':
                if not partial:
                    errors.append('chainGold is required')
            elif str(chain_gold) not in VALID_GOLDS:
                errors.append('invalid chainGold')
            else:
                cleaned['chainGold'] = str(chain_gold)
            if chain_color is None or str(chain_color) == '':
                if not partial:
                    errors.append('chainColor is required')
            elif str(chain_color) not in VALID_COLORS:
                errors.append('invalid chainColor')
            else:
                cleaned['chainColor'] = str(chain_color)
            length = clean_chain_length('chainLength', required=not partial)
            if length is not None:
                cleaned['chainLength'] = length

    return cleaned, ('; '.join(errors) if errors else None)


PRODUCT_NAME_MAX = 150
PRODUCT_DESC_MAX = 2000


def validate_product_fields(form, files, existing_image_ids_by_color=None):
    """Validates an admin product create/edit submission (multipart form).

    form: request.form (category/name/description/variant_* arrays/etc.)
    files: request.files (image_<color> file inputs; may be multiple per color)
    existing_image_ids_by_color: {color: [image_id, ...]} for edit mode.

    Returns (cleaned, error). On success (error is None), cleaned contains:
      category, name_zh, name_en, description_zh, description_en,
      default_color, is_published (bool),
      variants: [{'gold', 'carat', 'weight_chin', 'manual_price_twd'}, ...],
      uploads_by_color: {color: [FileStorage, ...]},
      remove_image_ids: set of ProductImage ids to delete,
      final_colors: set of colors the product will have images for afterward.
    """
    errors = []
    cleaned = {}
    existing_image_ids_by_color = {
        color: list(ids) for color, ids in (existing_image_ids_by_color or {}).items()
    }

    category = (form.get('category') or '').strip()
    if category not in VALID_CATEGORIES:
        errors.append('invalid category')
    else:
        cleaned['category'] = category

    name_zh = (form.get('name_zh') or '').strip()
    if not name_zh:
        errors.append('name_zh is required')
    elif len(name_zh) > PRODUCT_NAME_MAX:
        errors.append(f'name_zh must be at most {PRODUCT_NAME_MAX} characters')
    else:
        cleaned['name_zh'] = name_zh

    name_en = (form.get('name_en') or '').strip()
    if len(name_en) > PRODUCT_NAME_MAX:
        errors.append(f'name_en must be at most {PRODUCT_NAME_MAX} characters')
    cleaned['name_en'] = name_en[:PRODUCT_NAME_MAX] or None

    desc_zh = (form.get('description_zh') or '').strip()
    desc_en = (form.get('description_en') or '').strip()
    if len(desc_zh) > PRODUCT_DESC_MAX or len(desc_en) > PRODUCT_DESC_MAX:
        errors.append(f'description must be at most {PRODUCT_DESC_MAX} characters')
    cleaned['description_zh'] = desc_zh or None
    cleaned['description_en'] = desc_en or None

    default_color = (form.get('default_color') or 'white').strip()
    if default_color not in VALID_COLORS:
        errors.append('invalid default_color')
    else:
        cleaned['default_color'] = default_color

    cleaned['is_published'] = (form.get('is_published') or '').strip() in ('1', 'true', 'on')

    valid_carats = VALID_CARATS_CHAIN if category == 'chain' else VALID_CARATS
    golds = form.getlist('variant_gold')
    carats = form.getlist('variant_carat')
    weights = form.getlist('variant_weight')
    prices = form.getlist('variant_price')

    variants = []
    seen_keys = set()
    for i in range(max(len(golds), len(carats), len(weights), len(prices))):
        gold = (golds[i] if i < len(golds) else '').strip()
        carat = (carats[i] if i < len(carats) else '').strip()
        weight_raw = (weights[i] if i < len(weights) else '').strip()
        price_raw = (prices[i] if i < len(prices) else '').strip()
        if not gold and not carat and not weight_raw and not price_raw:
            continue  # blank row (e.g. an added-then-removed row)

        if gold not in VALID_GOLDS:
            errors.append(f'invalid variant metal: {gold or "(empty)"}')
            continue
        if carat not in valid_carats:
            errors.append(f'invalid variant carat: {carat or "(empty)"}')
            continue
        try:
            weight_chin = float(weight_raw)
            if weight_chin <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'invalid weight for {gold}/{carat}')
            continue

        manual_price_twd = None
        if price_raw:
            try:
                manual_price_twd = float(price_raw)
                if manual_price_twd < 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f'invalid manual price for {gold}/{carat}')
                continue

        key = (gold, carat)
        if key in seen_keys:
            errors.append(f'duplicate variant: {gold} / {carat}')
            continue
        seen_keys.add(key)
        variants.append({'gold': gold, 'carat': carat, 'weight_chin': weight_chin,
                          'manual_price_twd': manual_price_twd})

    if not variants:
        errors.append('at least one variant is required')
    cleaned['variants'] = variants

    uploads_by_color = {}
    for color in VALID_COLORS:
        file_list = [
            f for f in files.getlist(f'image_{color}')
            if f and getattr(f, 'filename', None)
        ]
        if file_list:
            uploads_by_color[color] = file_list

    remove_image_ids = set()
    for raw_id in form.getlist('remove_image_id'):
        try:
            remove_image_ids.add(int(raw_id))
        except (TypeError, ValueError):
            errors.append('invalid remove_image_id')

    image_order_ids = []
    for raw_id in form.getlist('image_order'):
        try:
            image_order_ids.append(int(raw_id))
        except (TypeError, ValueError):
            errors.append('invalid image_order')

    remaining_by_color = {}
    for color, ids in existing_image_ids_by_color.items():
        remaining = [img_id for img_id in ids if img_id not in remove_image_ids]
        if remaining:
            remaining_by_color[color] = remaining

    final_colors = set(remaining_by_color.keys()) | set(uploads_by_color.keys())
    if not final_colors:
        errors.append('at least one product image is required')
    elif default_color in VALID_COLORS and default_color not in final_colors:
        errors.append('default color must have at least one image')

    cleaned['uploads_by_color'] = uploads_by_color
    cleaned['remove_image_ids'] = remove_image_ids
    cleaned['image_order_ids'] = image_order_ids
    cleaned['final_colors'] = final_colors

    return cleaned, ('; '.join(errors) if errors else None)


def product_publish_ready(product):
    """Return (ready, message) for an existing product listing."""
    if not product.variants:
        return False, '請先新增至少一個款式選項。'
    if not product.images:
        return False, '請先上傳至少一張商品照片。'
    if not any(img.color == product.default_color for img in product.images):
        return False, '預設顏色必須至少有一張商品照片。'
    return True, None
