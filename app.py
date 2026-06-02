from flask import Flask, jsonify, request, abort, send_from_directory
from flask import g
from flask_cors import CORS
from sqlalchemy import create_engine, inspect, text, func
from sqlalchemy.orm import sessionmaker
from models import Base, Category, Enterprise, Product, User
import os
import json
import io
from PIL import Image
import uuid
import re
import unicodedata
from decimal import Decimal, DecimalException
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from validators import is_valid_email, is_valid_password, is_valid_brazil_phone, validate_base64_image
import sys
import jwt
import datetime
from functools import wraps
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.environ.get("DATA_DIR") or BASE_DIR
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "db.sqlite3")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_base64_image(data_url):
    if not data_url or not isinstance(data_url, str):
        return data_url

    data_url = data_url.strip()

    if not data_url.startswith("data:image/"):
        return data_url

    try:
        mime_type, file_data = validate_base64_image(data_url)

        ext = mime_type.split("/")[1].lower()
        if ext == "jpeg":
            ext = "jpg"

        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # compress/resize image to max 1080px while keeping aspect ratio
        try:
            image = Image.open(io.BytesIO(file_data))
            max_dim = 1080
            w, h = image.size
            if w > max_dim or h > max_dim:
                ratio = min(max_dim / w, max_dim / h)
                new_size = (int(w * ratio), int(h * ratio))
                image = image.resize(new_size, Image.LANCZOS)

            if ext in ("jpg", "jpeg"):
                image = image.convert("RGB")
                image.save(filepath, format="JPEG", quality=85, optimize=True)
            elif ext == "png":
                image.save(filepath, format="PNG", optimize=True)
            elif ext == "webp":
                image.save(filepath, format="WEBP", quality=85)
            elif ext == "gif":
                try:
                    image.save(filepath, format="GIF")
                except Exception:
                    image.convert("RGB").save(filepath, format="PNG", optimize=True)
            else:
                with open(filepath, "wb") as f:
                    f.write(file_data)
        except Exception:
            with open(filepath, "wb") as f:
                f.write(file_data)

        base_url = request.host_url.rstrip("/")
        return f"{base_url}/uploads/{filename}"

    except ValueError as e:
        abort(400, str(e))

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(bind=engine)

app = Flask(__name__)
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://test-vitrine.brizzigui.com",
                "https://vitrine.brizzigui.com",
            ]
        }
    },
)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self' https://test-vitrine.brizzigui.com https://vitrine.brizzigui.com; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response

PRICE_MODES = {"single", "range", "hidden"}
DEFAULT_CATEGORIES = ["Artesanato", "Alimentação", "Moda", "Plantas", "Cosmética", "Reciclagem"]
NAME_REQUIRED_ERROR = "name required"
INVALID_EMAIL_ERROR = "invalid email"


def ensure_schema():
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    if inspector.has_table("products"):
        columns = {column["name"] for column in inspector.get_columns("products")}
        if "images" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE products ADD COLUMN images JSON DEFAULT '[]'"))

    if inspector.has_table("categories"):
        columns = {column["name"] for column in inspector.get_columns("categories")}
        statements = []
        if "color" not in columns:
            statements.append("ALTER TABLE categories ADD COLUMN color TEXT")
        if "emoji" not in columns:
            statements.append("ALTER TABLE categories ADD COLUMN emoji TEXT")
        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))


ensure_schema()

# JWT auth configuration
load_dotenv()
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24


def _generate_token_for_user(user: User) -> str:
    payload = {
        "user_id": user.id,
        "role": user.role,
        "enterprise_id": user.enterprise_id,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXP_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def _get_token_from_header():
    auth = request.headers.get("Authorization")
    if not auth:
        abort(401, "authorization header missing")
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        abort(401, "invalid authorization header")
    return parts[1]


def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        abort(401, "token expired")
    except jwt.InvalidTokenError:
        abort(401, "invalid token")


def _get_current_token_payload():
    token = _get_token_from_header()
    return _decode_token(token)


def _require_admin():
    payload = _get_current_token_payload()
    if payload.get("role") != "admin":
        abort(403, "admin required")
    return payload


def _require_authenticated():
    return _get_current_token_payload()


def _require_admin_or_enterprise_owner(ent_id: str):
    payload = _get_current_token_payload()
    if payload.get("role") == "admin":
        return payload
    if payload.get("enterprise_id") == ent_id:
        return payload
    abort(403, "not authorized")


def _require_admin_or_same_user(user_id: str):
    payload = _get_current_token_payload()
    if payload.get("role") == "admin" or payload.get("user_id") == user_id:
        return payload
    abort(403, "not authorized")


def _coerce_price_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(Decimal("0.00"))
        except DecimalException:
            return None
    if isinstance(value, str):
        try:
            return Decimal(value).quantize(Decimal("0.00"))
        except DecimalException:
            return None
    return None


def _slugify(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized


def _category_to_dict(category: Category) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "color": category.color,
        "emoji": category.emoji,
    }


def _ensure_default_categories(session) -> None:
    if session.query(Category).count() > 0:
        return
    for name in DEFAULT_CATEGORIES:
        slug = _slugify(name) or f"category-{uuid.uuid4().hex[:8]}"
        cat_id = slug
        if session.get(Category, cat_id):
            cat_id = f"{slug}-{uuid.uuid4().hex[:6]}"
        session.add(Category(id=cat_id, name=name, color=None, emoji=None))
    session.commit()


def _get_category_by_id_or_name(session, cat_id: str) -> Category | None:
    category = session.get(Category, cat_id)
    if category:
        return category
    return session.query(Category).filter(Category.name == cat_id).first()


def _infer_product_price_mode(product: Product) -> str:
    mode = (product.price_mode or "").strip().lower()
    if mode in PRICE_MODES:
        return mode
    if product.price_min is not None and product.price_max is not None:
        return "range"
    return "single"


def _resolve_product_price_mode(payload: dict, current_product: Product | None = None) -> str:
    raw_mode = payload.get("priceMode")
    if raw_mode is None:
        return "single" if current_product is None else _infer_product_price_mode(current_product)
    return str(raw_mode).strip().lower()


def _hidden_price_payload() -> dict:
    return {
        "price_mode": "hidden",
        "price": Decimal("0.00"),
        "price_min": None,
        "price_max": None,
    }


def _single_price_payload(payload: dict, current_product: Product | None = None) -> dict:
    current_price = current_product.price if current_product is not None else None
    price_value = payload.get("price", current_price)
    price = _coerce_price_number(price_value)
    if price is None:
        abort(400, "price obrigatório para modo single")
    if price < 0:
        abort(400, "valores de preço não podem ser negativos")
    return {
        "price_mode": "single",
        "price": price,
        "price_min": None,
        "price_max": None,
    }


def _range_price_payload(payload: dict, current_product: Product | None = None) -> dict:
    current_price_min = current_product.price_min if current_product is not None else None
    current_price_max = current_product.price_max if current_product is not None else None
    price_min_value = payload.get("priceMin", current_price_min)
    price_max_value = payload.get("priceMax", current_price_max)
    price_min = _coerce_price_number(price_min_value)
    price_max = _coerce_price_number(price_max_value)

    if price_min is None or price_max is None:
        abort(400, "priceMin e priceMax obrigatórios para modo range")
    if price_min < 0 or price_max < 0:
        abort(400, "valores de preço não podem ser negativos")
    if price_min > price_max:
        abort(400, "priceMin não pode ser maior que priceMax")

    return {
        "price_mode": "range",
        "price": price_min,
        "price_min": price_min,
        "price_max": price_max,
    }


def normalize_product_payload(payload: dict, current_product: Product | None = None) -> dict:
    mode = _resolve_product_price_mode(payload, current_product)
    if mode not in PRICE_MODES:
        abort(400, "priceMode inválido")

    if mode == "hidden":
        return _hidden_price_payload()
    if mode == "single":
        return _single_price_payload(payload, current_product)
    return _range_price_payload(payload, current_product)


def _normalize_image_list(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        abort(400, "images deve ser uma lista")

    processed_images = []
    for image in value:
        if not image:
            continue
        if not isinstance(image, str):
            abort(400, "images deve conter apenas strings")
        processed_images.append(process_base64_image(image))

    return processed_images


def _product_images(product: Product) -> list[str]:
    images = product.images or []
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except json.JSONDecodeError:
            images = []
    if not isinstance(images, list):
        images = []

    clean_images = [
        image.strip()
        for image in images
        if isinstance(image, str) and image.strip()
    ]

    primary_image = (product.image or "").strip()
    if primary_image and primary_image not in clean_images:
        clean_images.insert(0, primary_image)

    return clean_images


def normalize_product_images_payload(payload: dict, current_product: Product | None = None) -> list[str]:
    if "images" in payload:
        images = _normalize_image_list(payload.get("images"))
        if not images and payload.get("image"):
            image = process_base64_image(payload.get("image"))
            return [image] if image else []
        return images

    if "image" in payload:
        image = process_base64_image(payload.get("image"))
        return [image] if image else []

    if current_product is not None:
        return _product_images(current_product)

    return []


def product_to_dict(product: Product) -> dict:
    mode = _infer_product_price_mode(product)
    images = _product_images(product)
    primary_image = images[0] if images else ""

    if mode == "range":
        price_min = product.price_min
        price_max = product.price_max
        if price_min is None:
            price_min = product.price
        if price_max is None:
            price_max = product.price
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description or "",
            "image": primary_image,
            "images": images,
            "price": float(price_min or 0.0),
            "priceMode": "range",
            "priceMin": float(price_min or 0.0),
            "priceMax": float(price_max or 0.0),
        }

    if mode == "hidden":
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description or "",
            "image": primary_image,
            "images": images,
            "price": 0.0,
            "priceMode": "hidden",
            "priceMin": None,
            "priceMax": None,
        }

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description or "",
        "image": primary_image,
        "images": images,
        "price": float(product.price or 0.0),
        "priceMode": "single",
        "priceMin": None,
        "priceMax": None,
    }


def enterprise_to_dict(ent: Enterprise):
    return {
        "id": ent.id,
        "name": ent.name,
        "category": ent.category,
        "coverImage": ent.cover_image,
        "description": ent.short_description or "",
        "fullDescription": ent.full_description or "",
        "whatsapp": ent.whatsapp or "",
        "instagram": ent.instagram or "",
        "email": ent.email or "",
        "tags": ent.tags or [],
        "products": [product_to_dict(p) for p in ent.products],
    }


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/categories", methods=["GET", "POST"])
def categories_list_create():
    session = Session()
    _ensure_default_categories(session)

    if request.method == "GET":
        cats = session.query(Category).order_by(Category.name).all()
        if request.args.get("format") == "objects":
            data = [_category_to_dict(cat) for cat in cats]
        else:
            data = [cat.name for cat in cats]
        session.close()
        return jsonify(data)
    # POST: admin only
    payload = request.json or {}
    _require_admin()
    name = (payload.get("name") or "").strip()
    if not name:
        session.close()
        abort(400, NAME_REQUIRED_ERROR)

    color = payload.get("color")
    emoji = payload.get("emoji")

    existing = session.query(Category).filter(func.lower(Category.name) == name.lower()).first()
    if existing:
        session.close()
        abort(409, "category already exists")

    slug = _slugify(name) or f"category-{uuid.uuid4().hex[:8]}"
    cat_id = slug
    if session.get(Category, cat_id):
        cat_id = f"{slug}-{uuid.uuid4().hex[:6]}"

    category = Category(id=cat_id, name=name, color=color, emoji=emoji)
    session.add(category)
    session.commit()
    data = _category_to_dict(category)
    session.close()
    return jsonify(data), 201


def _category_detail_response(session, category: Category):
    data = _category_to_dict(category)
    session.close()
    return jsonify(data)


def _update_category_response(session, category: Category):
    _require_admin()
    payload = request.json or {}
    name = (payload.get("name") or "").strip()
    if not name:
        session.close()
        abort(400, NAME_REQUIRED_ERROR)

    if "color" in payload:
        category.color = payload.get("color")
    if "emoji" in payload:
        category.emoji = payload.get("emoji")

    existing = session.query(Category).filter(func.lower(Category.name) == name.lower()).first()
    if existing and existing.id != category.id:
        session.close()
        abort(409, "category already exists")

    old_name = category.name
    if name != old_name:
        category.name = name
        ents = session.query(Enterprise).filter(Enterprise.category == old_name).all()
        for ent in ents:
            ent.category = name
            session.add(ent)

    session.add(category)
    session.commit()
    data = _category_to_dict(category)
    session.close()
    return jsonify(data)


def _delete_category_response(session, category: Category):
    _require_admin()
    in_use = session.query(Enterprise).filter(Enterprise.category == category.name).first()
    if in_use:
        session.close()
        abort(409, "category in use")

    session.delete(category)
    session.commit()
    session.close()
    return jsonify({"ok": True})


@app.route("/api/categories/<string:cat_id>", methods=["GET", "PUT", "DELETE"])
def category_detail(cat_id):
    session = Session()
    category = _get_category_by_id_or_name(session, cat_id)
    if not category:
        session.close()
        abort(404)

    if request.method == "GET":
        return _category_detail_response(session, category)
    if request.method == "PUT":
        return _update_category_response(session, category)
    return _delete_category_response(session, category)


@app.route("/api/enterprises", methods=["GET", "POST"])
def enterprises_list_create():
    session = Session()
    if request.method == "GET":
        ents = session.query(Enterprise).all()
        data = [enterprise_to_dict(e) for e in ents]
        session.close()
        return jsonify(data)

    # creating an enterprise requires authentication (owner or admin)
    _require_authenticated()
    payload = request.json or {}
    if not payload.get("name"):
        abort(400, NAME_REQUIRED_ERROR)
    # validate optional contact fields
    if payload.get("email") and not is_valid_email(payload.get("email")):
        abort(400, INVALID_EMAIL_ERROR)
    if payload.get("whatsapp") and not is_valid_brazil_phone(payload.get("whatsapp")):
        abort(400, "invalid phone")
    new = Enterprise(
        id=payload.get("id") or payload["name"].lower().replace(" ", "-")[:80],
        name=payload["name"],
        category=payload.get("category", "Artesanato"),
        cover_image=process_base64_image(payload.get("coverImage")),
        short_description=payload.get("description"),
        full_description=payload.get("fullDescription"),
        whatsapp=payload.get("whatsapp"),
        instagram=payload.get("instagram"),
        email=payload.get("email"),
        tags=payload.get("tags", []),
    )
    session.add(new)
    session.commit()
    data = enterprise_to_dict(new)
    session.close()
    return jsonify(data), 201


def _enterprise_detail_response(session, ent: Enterprise):
    data = enterprise_to_dict(ent)
    session.close()
    return jsonify(data)


def _apply_enterprise_updates(ent: Enterprise, payload: dict) -> None:
    direct_fields = {
        "tags": "tags",
        "name": "name",
        "category": "category",
        "instagram": "instagram",
    }
    renamed_fields = {
        "coverImage": ("cover_image", process_base64_image),
        "description": ("short_description", lambda value: value),
        "fullDescription": ("full_description", lambda value: value),
    }

    for key, value in payload.items():
        if key in direct_fields:
            setattr(ent, direct_fields[key], value)
        elif key in renamed_fields:
            attr_name, transform = renamed_fields[key]
            setattr(ent, attr_name, transform(value))
        elif key == "whatsapp":
            if value and not is_valid_brazil_phone(value):
                abort(400, "invalid phone")
            ent.whatsapp = value
        elif key == "email":
            if value and not is_valid_email(value):
                abort(400, INVALID_EMAIL_ERROR)
            ent.email = value


def _update_enterprise_response(session, ent: Enterprise, ent_id: str):
    _require_admin_or_enterprise_owner(ent_id)
    payload = request.json or {}
    _apply_enterprise_updates(ent, payload)
    session.add(ent)
    session.commit()
    data = enterprise_to_dict(ent)
    session.close()
    return jsonify(data)


def _delete_enterprise_response(session, ent: Enterprise, ent_id: str):
    _require_admin_or_enterprise_owner(ent_id)
    session.delete(ent)
    session.commit()
    session.close()
    return jsonify({"ok": True})


@app.route("/api/enterprises/<string:ent_id>", methods=["GET", "PUT", "DELETE"])
def enterprise_detail(ent_id):
    session = Session()
    ent = session.get(Enterprise, ent_id)
    if not ent:
        session.close()
        abort(404)
    if request.method == "GET":
        return _enterprise_detail_response(session, ent)
    if request.method == "PUT":
        return _update_enterprise_response(session, ent, ent_id)
    return _delete_enterprise_response(session, ent, ent_id)


@app.route("/api/enterprises/<string:ent_id>/products", methods=["POST"])
def create_product(ent_id):
    session = Session()
    ent = session.get(Enterprise, ent_id)
    if not ent:
        session.close()
        abort(404)
    # only admin or enterprise owner
    _require_admin_or_enterprise_owner(ent_id)
    payload = request.json or {}
    if not payload.get("name"):
        abort(400, NAME_REQUIRED_ERROR)
    normalized_price = normalize_product_payload(payload)
    product_images = normalize_product_images_payload(payload)
    pid = payload.get("id") or f"{ent_id}-{int(__import__('time').time())}"
    prod = Product(
        id=pid,
        enterprise_id=ent_id,
        name=payload["name"],
        description=payload.get("description"),
        price=normalized_price["price"],
        price_mode=normalized_price["price_mode"],
        price_min=normalized_price["price_min"],
        price_max=normalized_price["price_max"],
        image=product_images[0] if product_images else "",
        images=product_images,
    )
    session.add(prod)
    session.commit()
    data = product_to_dict(prod)
    session.close()
    return jsonify(data), 201


@app.route("/api/enterprises/<string:ent_id>/products/<string:prod_id>", methods=["PUT", "DELETE"])
def modify_product(ent_id, prod_id):
    session = Session()
    prod = session.get(Product, prod_id)
    if not prod or prod.enterprise_id != ent_id:
        session.close()
        abort(404)
    # only admin or enterprise owner
    _require_admin_or_enterprise_owner(ent_id)
    if request.method == "PUT":
        payload = request.json or {}
        for k, v in payload.items():
            if k == "name":
                prod.name = v
            elif k == "description":
                prod.description = v
        if "images" in payload or "image" in payload:
            product_images = normalize_product_images_payload(payload, current_product=prod)
            prod.image = product_images[0] if product_images else ""
            prod.images = product_images
        normalized_price = normalize_product_payload(payload, current_product=prod)
        prod.price = normalized_price["price"]
        prod.price_mode = normalized_price["price_mode"]
        prod.price_min = normalized_price["price_min"]
        prod.price_max = normalized_price["price_max"]
        session.add(prod)
        session.commit()
        data = product_to_dict(prod)
        session.close()
        return jsonify(data)

    session.delete(prod)
    session.commit()
    session.close()
    return jsonify({"ok": True})


@app.route("/api/users", methods=["GET", "POST"])
def users_list_create():
    session = Session()
    if request.method == "GET":
        # listing users is admin-only
        _require_admin()
        users = session.query(User).all()
        data = [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "enterpriseId": u.enterprise_id, "active": u.active} for u in users]
        session.close()
        return jsonify(data)

    # creating users is admin-only (no public signup)
    _require_admin()
    payload = request.json or {}
    if not payload.get("email") or not payload.get("password"):
        abort(400, "email and password required")
    # validate email and password
    if not is_valid_email(payload.get("email")):
        abort(400, INVALID_EMAIL_ERROR)
    if not is_valid_password(payload.get("password")):
        abort(400, "password must be at least 10 characters")
    new = User(
        id=payload.get("id") or f"user-{int(__import__('time').time())}",
        email=payload["email"],
        password=generate_password_hash(payload["password"], method="pbkdf2:sha256", salt_length=16),
        name=payload.get("name"),
        role=payload.get("role", "owner"),
        enterprise_id=payload.get("enterpriseId"),
        active=payload.get("active", True),
    )
    session.add(new)
    session.commit()
    data = {"id": new.id, "email": new.email, "name": new.name, "role": new.role, "enterpriseId": new.enterprise_id, "active": new.active}
    session.close()
    return jsonify(data), 201


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "enterpriseId": user.enterprise_id,
        "active": user.active,
    }


def _apply_user_updates(user: User, payload: dict) -> None:
    direct_fields = {
        "name": "name",
        "role": "role",
        "enterpriseId": "enterprise_id",
        "active": "active",
    }

    if "email" in payload:
        if not is_valid_email(payload["email"]):
            abort(400, INVALID_EMAIL_ERROR)
        user.email = payload["email"]

    if "password" in payload and payload["password"]:
        if not is_valid_password(payload["password"]):
            abort(400, "password must be at least 10 characters")
        user.password = generate_password_hash(payload["password"], method="pbkdf2:sha256", salt_length=16)

    for key, attr_name in direct_fields.items():
        if key in payload:
            setattr(user, attr_name, payload[key])


def _update_user_response(session, user: User, user_id: str):
    _require_admin_or_same_user(user_id)
    payload = request.json or {}
    _apply_user_updates(user, payload)
    session.add(user)
    session.commit()
    data = _user_to_dict(user)
    session.close()
    return jsonify(data)


def _delete_user_response(session, user: User, user_id: str):
    _require_admin_or_same_user(user_id)
    session.delete(user)
    session.commit()
    session.close()
    return jsonify({"ok": True})


@app.route("/api/users/<string:user_id>", methods=["PUT", "DELETE"])
def update_delete_user(user_id):
    session = Session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        abort(404, "User not found")
    if request.method == "PUT":
        return _update_user_response(session, user, user_id)
    return _delete_user_response(session, user, user_id)


@app.route("/api/login", methods=["POST"])
def login():
    payload = request.json or {}
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        abort(400, "email and password required")
    # validate formats
    if not is_valid_email(email):
        abort(400, INVALID_EMAIL_ERROR)
    if not is_valid_password(password):
        abort(400, "invalid password")
    session = Session()
    user = session.query(User).filter_by(email=email, active=True).first()
    if not user or not check_password_hash(user.password, password):
        session.close()
        return jsonify({"ok": False}), 401

    token = _generate_token_for_user(user)
    data = {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "enterpriseId": user.enterprise_id, "active": user.active, "token": token}
    session.close()
    return jsonify(data)


@app.route("/uploads/<name>", methods=["GET"])
def download_file(name):
    return send_from_directory(UPLOAD_FOLDER, name)

@app.route("/api/upload", methods=["POST"])
def upload_file():
    # require authentication for uploads
    _require_authenticated()

    if 'file' not in request.files:
        abort(400, "No file part")
    file = request.files['file']
    if file.filename == '':
        abort(400, "No selected file")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        try:
            file.stream.seek(0)
            image = Image.open(file.stream)
            max_dim = 1080
            w, h = image.size
            if w > max_dim or h > max_dim:
                ratio = min(max_dim / w, max_dim / h)
                new_size = (int(w * ratio), int(h * ratio))
                image = image.resize(new_size, Image.LANCZOS)

            if ext in ("jpg", "jpeg"):
                image = image.convert("RGB")
                image.save(filepath, format="JPEG", quality=85, optimize=True)
            elif ext == "png":
                image.save(filepath, format="PNG", optimize=True)
            elif ext == "webp":
                image.save(filepath, format="WEBP", quality=85)
            elif ext == "gif":
                try:
                    image.save(filepath, format="GIF")
                except Exception:
                    image.convert("RGB").save(filepath, format="PNG", optimize=True)
            else:
                file.stream.seek(0)
                with open(filepath, "wb") as f:
                    f.write(file.stream.read())
        except Exception:
            file.stream.seek(0)
            with open(filepath, "wb") as f:
                f.write(file.stream.read())
        return jsonify({"url": f"/uploads/{unique_filename}", "filename": unique_filename}), 201
    else:
        abort(400, "Invalid file type")


if __name__ == "__main__":
    # create DB if missing
    if not os.path.exists(DB_PATH):
        print("DB not found, run init_db.py to create and seed the database.")
    if len(sys.argv) == 3:
      port = int(sys.argv[1])
      debug = bool(sys.argv[2] == "True")
    app.run(host="0.0.0.0", port=port, debug=debug)
