import os
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Product, Enterprise
from seed_data import ENTERPRISES


BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")


def reset_products_table(engine):
    # Drop and recreate only products table; enterprises/users remain untouched.
    Product.__table__.drop(engine, checkfirst=True)
    Product.__table__.create(engine, checkfirst=True)


def seed_products(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    existing_enterprise_ids = {row[0] for row in session.query(Enterprise.id).all()}

    for enterprise in ENTERPRISES:
        ent_id = enterprise.get("id")
        if ent_id not in existing_enterprise_ids:
            continue

        for p in enterprise.get("products", []):
            prod = Product(
                id=p["id"],
                enterprise_id=ent_id,
                name=p["name"],
                description=p.get("description"),
                price=p.get("price", 0.0),
                price_mode="single",
                price_min=None,
                price_max=None,
                image=p.get("image"),
            )
            session.add(prod)

    session.commit()
    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reset only products table, preserving enterprises and users."
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Populate products from seed_data after reset.",
    )
    args = parser.parse_args()

    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)

    reset_products_table(engine)

    if args.seed:
        seed_products(engine)
        print("Products table reset and seeded successfully.")
    else:
        print("Products table reset successfully (no products seeded).")


if __name__ == "__main__":
    main()
