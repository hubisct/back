from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import JSON

Base = declarative_base()


class Enterprise(Base):
    __tablename__ = "enterprises"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    cover_image = Column(Text)
    short_description = Column(Text)
    full_description = Column(Text)
    whatsapp = Column(String)
    instagram = Column(String)
    email = Column(String)
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="enterprise", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)
    enterprise_id = Column(String, ForeignKey("enterprises.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, default=0.0)
    price_mode = Column(String, nullable=True)
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    image = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="products")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    enterprise_id = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String)
    role = Column(String, default="owner")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
