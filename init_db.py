import json
import re
import unicodedata
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from models import Base, Category, Enterprise, Product, User
from seed_data import ENTERPRISES, USERS
import os
from decimal import Decimal


data_dir = os.environ.get("DATA_DIR") or os.path.dirname(__file__)
os.makedirs(data_dir, exist_ok=True)
DB_PATH = os.path.join(data_dir, "db.sqlite3")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(bind=engine)

DEFAULT_CATEGORIES = ["Artesanato", "Alimentação", "Moda", "Plantas", "Cosmética", "Reciclagem"]
PASSWORD_HASH_METHOD = "pbkdf2:sha256"


def _slugify(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized


def _collect_category_names() -> set[str]:
    category_names = set(DEFAULT_CATEGORIES)
    for enterprise in ENTERPRISES:
        if enterprise.get("category"):
            category_names.add(enterprise["category"])
    return category_names


def _seed_categories(session) -> None:
    category_names = _collect_category_names()
    for name in sorted(category_names):
        existing = session.query(Category).filter_by(name=name).first()
        if existing:
            continue
        slug = _slugify(name) or f"category-{uuid.uuid4().hex[:8]}"
        cat_id = slug
        if session.get(Category, cat_id):
            cat_id = f"{slug}-{uuid.uuid4().hex[:6]}"
        session.add(Category(id=cat_id, name=name, color=None, emoji=None))


def _normalize_seed_product_price(product: dict) -> dict:
    price_mode = product.get("price_mode") or "single"
    price_min = product.get("price_min")
    price_max = product.get("price_max")
    price = product.get("price", Decimal("0.00"))

    if price_mode == "range":
        if price_min is None:
            price_min = price
        if price_max is None:
            price_max = price_min
        price = price_min
    elif price_mode == "hidden":
        price = Decimal("0.00")
        price_min = None
        price_max = None
    else:
        price_mode = "single"
        price_min = None
        price_max = None

    return {
        "price": price,
        "price_mode": price_mode,
        "price_min": price_min,
        "price_max": price_max,
    }


def _seed_product(session, enterprise_id: str, product: dict) -> None:
    normalized_price = _normalize_seed_product_price(product)
    prod = Product(
        id=product["id"],
        enterprise_id=enterprise_id,
        name=product["name"],
        description=product.get("description"),
        price=normalized_price["price"],
        price_mode=normalized_price["price_mode"],
        price_min=normalized_price["price_min"],
        price_max=normalized_price["price_max"],
        image=product.get("image"),
        images=product.get("images") or ([product.get("image")] if product.get("image") else []),
    )
    session.add(prod)


def _seed_enterprises_and_products(session) -> None:
    for e in ENTERPRISES:
        ent = Enterprise(
            id=e["id"],
            name=e["name"],
            category=e.get("category", "Outros"),
            cover_image=e.get("cover_image"),
            short_description=e.get("short_description"),
            full_description=e.get("full_description"),
            whatsapp=e.get("whatsapp"),
            instagram=e.get("instagram"),
            email=e.get("email"),
            tags=e.get("tags", []),
        )
        session.add(ent)
        for p in e.get("products", []):
            _seed_product(session, e["id"], p)


def _seed_users(session) -> None:
    for u in USERS:
        existing_user = session.query(User).filter_by(id=u["id"]).first()
        if not existing_user:
            user = User(
                id=u["id"],
                email=u["email"],
                password=generate_password_hash(u["password"], method=PASSWORD_HASH_METHOD, salt_length=16),
                name=u.get("name"),
                role=u.get("role", "owner"),
                active=u.get("active", True),
                enterprise_id=u.get("enterprise_id"),
            )
            session.add(user)


def _upgrade_plain_text_passwords(session) -> None:
    all_users = session.query(User).all()
    for db_user in all_users:
        if not db_user.password.startswith(PASSWORD_HASH_METHOD):
            db_user.password = generate_password_hash(db_user.password, method=PASSWORD_HASH_METHOD, salt_length=16)
            session.add(db_user)


def init_db(drop=False):
    if drop and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    Base.metadata.create_all(engine)

    session = Session()
    _seed_categories(session)
    _seed_enterprises_and_products(session)
    _seed_users(session)
    _upgrade_plain_text_passwords(session)
    session.commit()
    session.close()


if __name__ == "__main__":
    print("Initializing database and seeding data...")
    init_db(drop=False)
    print("Done. DB created at:", DB_PATH)
