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
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
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
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "price": float(p.price or 0.0),
                "image": p.image or "",
            }
            for p in ent.products
        ],
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
    pid = payload.get("id") or f"{ent_id}-{int(__import__('time').time())}"
    prod = Product(
        id=pid,
        enterprise_id=ent_id,
        name=payload["name"],
        description=payload.get("description"),
        price=payload.get("price", 0.0),
        image=process_base64_image(payload.get("image")),
    )
    session.add(prod)
    session.commit()
    data = {
        "id": prod.id,
        "name": prod.name,
        "description": prod.description,
        "price": float(prod.price or 0.0),
        "image": prod.image or "",
    }
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
            elif k == "price":
                prod.price = v
            elif k == "image":
                prod.image = process_base64_image(v)
        session.add(prod)
        session.commit()
        data = {"id": prod.id, "name": prod.name, "description": prod.description, "price": float(prod.price or 0.0), "image": prod.image}
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


@app.route("/api/users/<string:user_id>", methods=["PUT", "DELETE"])
def update_delete_user(user_id):
    session = Session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        abort(404, "User not found")

    if request.method == "PUT":
        payload = request.json or {}
        
        # Validate email if provided
        if "email" in payload:
            if not is_valid_email(payload["email"]):
                abort(400, "invalid email")
            user.email = payload["email"]
            
        # Validate password if provided
        if "password" in payload and payload["password"]:
            if not is_valid_password(payload["password"]):
                abort(400, "password must be at least 10 characters")
            user.password = generate_password_hash(payload["password"], method="pbkdf2:sha256", salt_length=16)

        if "name" in payload:
            user.name = payload["name"]
        if "role" in payload:
            user.role = payload["role"]
        if "enterpriseId" in payload:
            user.enterprise_id = payload["enterpriseId"]
        if "active" in payload:
            user.active = payload["active"]

        session.add(user)
        session.commit()
        data = {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "enterpriseId": user.enterprise_id, "active": user.active}
        session.close()
        return jsonify(data)

    if request.method == "DELETE":
        session.delete(user)
        session.commit()
        session.close()
        return jsonify({"ok": True})


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
    
    if not user:
        session.close()
        return jsonify({"ok": False}), 401
        
    # Verifica se a senha está armazenada em texto puro (legado) e atualiza para hash
    if user.password == password:
        user.password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        session.add(user)
        session.commit()
    elif not check_password_hash(user.password, password):
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
