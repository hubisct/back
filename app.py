from flask import Flask, jsonify, request, abort, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Enterprise, Product, User
import os
import json
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from validators import is_valid_email, is_valid_password, is_valid_brazil_phone, validate_base64_image

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

        with open(filepath, "wb") as f:
            f.write(file_data)

        base_url = request.host_url.rstrip("/")
        return f"{base_url}/uploads/{filename}"

    except ValueError as e:
        abort(400, str(e))

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(bind=engine)

app = Flask(__name__)
CORS(app)

PRICE_MODES = {"single", "range", "hidden"}


def _coerce_price_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _infer_product_price_mode(product: Product) -> str:
    mode = (product.price_mode or "").strip().lower()
    if mode in PRICE_MODES:
        return mode
    if product.price_min is not None and product.price_max is not None:
        return "range"
    return "single"


def normalize_product_payload(payload: dict, current_product: Product | None = None) -> dict:
    raw_mode = payload.get("priceMode")
    if raw_mode is None:
        if current_product is None:
            mode = "single"
        else:
            mode = _infer_product_price_mode(current_product)
    else:
        mode = str(raw_mode).strip().lower()

    if mode not in PRICE_MODES:
        abort(400, "priceMode inválido")

    current_price = current_product.price if current_product is not None else None
    current_price_min = current_product.price_min if current_product is not None else None
    current_price_max = current_product.price_max if current_product is not None else None

    if mode == "hidden":
        return {
            "price_mode": "hidden",
            "price": 0.0,
            "price_min": None,
            "price_max": None,
        }

    if mode == "single":
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


def product_to_dict(product: Product) -> dict:
    mode = _infer_product_price_mode(product)
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
            "image": product.image or "",
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
            "image": product.image or "",
            "price": 0.0,
            "priceMode": "hidden",
            "priceMin": None,
            "priceMax": None,
        }

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description or "",
        "image": product.image or "",
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


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/categories")
def get_categories():
    # simple static categories used in frontend
    cats = ["Artesanato", "Alimentação", "Moda", "Plantas", "Cosmética", "Reciclagem"]
    return jsonify(cats)


@app.route("/api/enterprises", methods=["GET", "POST"])
def enterprises_list_create():
    session = Session()
    if request.method == "GET":
        ents = session.query(Enterprise).all()
        data = [enterprise_to_dict(e) for e in ents]
        session.close()
        return jsonify(data)

    payload = request.json or {}
    if not payload.get("name"):
        abort(400, "name required")
    # validate optional contact fields
    if payload.get("email") and not is_valid_email(payload.get("email")):
        abort(400, "invalid email")
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


@app.route("/api/enterprises/<string:ent_id>", methods=["GET", "PUT", "DELETE"])
def enterprise_detail(ent_id):
    session = Session()
    ent = session.get(Enterprise, ent_id)
    if not ent:
        session.close()
        abort(404)
    if request.method == "GET":
        data = enterprise_to_dict(ent)
        session.close()
        return jsonify(data)

    if request.method == "PUT":
        payload = request.json or {}
        for k, v in payload.items():
            if k == "coverImage":
                ent.cover_image = process_base64_image(v)
            elif k == "description":
                ent.short_description = v
            elif k == "fullDescription":
                ent.full_description = v
            elif k == "tags":
                ent.tags = v
            elif k == "name":
                ent.name = v
            elif k == "category":
                ent.category = v
            elif k == "whatsapp":
                if v and not is_valid_brazil_phone(v):
                    abort(400, "invalid phone")
                ent.whatsapp = v
            elif k == "instagram":
                ent.instagram = v
            elif k == "email":
                if v and not is_valid_email(v):
                    abort(400, "invalid email")
                ent.email = v
        session.add(ent)
        session.commit()
        data = enterprise_to_dict(ent)
        session.close()
        return jsonify(data)

    # DELETE
    session.delete(ent)
    session.commit()
    session.close()
    return jsonify({"ok": True})


@app.route("/api/enterprises/<string:ent_id>/products", methods=["POST"])
def create_product(ent_id):
    session = Session()
    ent = session.get(Enterprise, ent_id)
    if not ent:
        session.close()
        abort(404)
    payload = request.json or {}
    if not payload.get("name"):
        abort(400, "name required")
    normalized_price = normalize_product_payload(payload)
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
        image=process_base64_image(payload.get("image")),
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
    if request.method == "PUT":
        payload = request.json or {}
        for k, v in payload.items():
            if k == "name":
                prod.name = v
            elif k == "description":
                prod.description = v
            elif k == "image":
                prod.image = process_base64_image(v)
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
        users = session.query(User).all()
        data = [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "enterpriseId": u.enterprise_id, "active": u.active} for u in users]
        session.close()
        return jsonify(data)

    payload = request.json or {}
    if not payload.get("email") or not payload.get("password"):
        abort(400, "email and password required")
    # validate email and password
    if not is_valid_email(payload.get("email")):
        abort(400, "invalid email")
    if not is_valid_password(payload.get("password")):
        abort(400, "password must be at least 10 characters")
    new = User(
        id=payload.get("id") or f"user-{int(__import__('time').time())}",
        email=payload["email"],
        password=generate_password_hash(payload["password"]),
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


@app.route("/api/login", methods=["POST"])
def login():
    payload = request.json or {}
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        abort(400, "email and password required")
    # validate formats
    if not is_valid_email(email):
        abort(400, "invalid email")
    if not is_valid_password(password):
        abort(400, "invalid password")
    session = Session()
    user = session.query(User).filter_by(email=email, active=True).first()
    if not user or not check_password_hash(user.password, password):
        session.close()
        return jsonify({"ok": False}), 401
    data = {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "enterpriseId": user.enterprise_id, "active": user.active}
    session.close()
    return jsonify(data)


@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(UPLOAD_FOLDER, name)

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        abort(400, "No file part")
    file = request.files['file']
    if file.filename == '':
        abort(400, "No selected file")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
        return jsonify({"url": f"/uploads/{unique_filename}", "filename": unique_filename}), 201
    else:
        abort(400, "Invalid file type")


if __name__ == "__main__":
    # create DB if missing
    if not os.path.exists(DB_PATH):
        print("DB not found, run init_db.py to create and seed the database.")
    app.run(host="0.0.0.0", port=5174)
