from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import JSON

Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"
    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String)
    emoji = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    price = Column(Numeric(10, 2), default=0.0)
    price_mode = Column(String, nullable=True)
    price_min = Column(Numeric(10, 2), nullable=True)
    price_max = Column(Numeric(10, 2), nullable=True)
    image = Column(Text)
    images = Column(JSON, default=[])
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


class SupportRequest(Base):
    __tablename__ = "support_requests"
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
