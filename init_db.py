import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from models import Base, Enterprise, Product, User
from seed_data import ENTERPRISES, USERS
import os


DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite3")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(bind=engine)


def init_db(drop=False):
    if drop and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    Base.metadata.create_all(engine)

    session = Session()

    # Seed enterprises and products
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
            price_mode = p.get("price_mode") or "single"
            price_min = p.get("price_min")
            price_max = p.get("price_max")
            price = p.get("price", 0.0)
            if price_mode == "range":
                if price_min is None:
                    price_min = price
                if price_max is None:
                    price_max = price_min
                price = price_min
            elif price_mode == "hidden":
                price = 0.0
                price_min = None
                price_max = None
            else:
                price_mode = "single"
                price_min = None
                price_max = None

            prod = Product(
                id=p["id"],
                enterprise_id=e["id"],
                name=p["name"],
                description=p.get("description"),
                price=price,
                price_mode=price_mode,
                price_min=price_min,
                price_max=price_max,
                image=p.get("image"),
            )
            session.add(prod)

    # Seed users
    for u in USERS:
        user = User(
            id=u["id"],
            email=u["email"],
            password=generate_password_hash(u["password"]),
            name=u.get("name"),
            role=u.get("role", "owner"),
            active=u.get("active", True),
            enterprise_id=u.get("enterprise_id"),
        )
        session.add(user)

    session.commit()
    session.close()


if __name__ == "__main__":
    print("Initializing database and seeding data...")
    init_db(drop=False)
    print("Done. DB created at:", DB_PATH)
