import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    reset_token = Column(String, nullable=True)

    # Relationships
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="products")
    links = relationship("ProductLink", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="product", cascade="all, delete-orphan")


class ProductLink(Base):
    __tablename__ = "product_links"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    website = Column(String, nullable=False)  # 'amazon', 'flipkart', 'myntra', etc.
    current_price = Column(Float, nullable=True)
    currency = Column(String, default="INR")
    last_scraped_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    in_stock = Column(Boolean, default=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="links")
    price_history = relationship("PriceHistory", back_populates="product_link", cascade="all, delete-orphan")
    offers = relationship("Offer", back_populates="product_link", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_link_id = Column(Integer, ForeignKey("product_links.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    product_link = relationship("ProductLink", back_populates="price_history")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)  # For WhatsApp alerts
    target_price = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True)
    alert_type = Column(String, default="target_price")  # target_price, percentage_drop, historical_low, deal_score, new_historical_low, cross_store
    alert_condition_value = Column(Float, nullable=True)  # threshold for the alert type
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="alerts")


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    product_link_id = Column(Integer, ForeignKey("product_links.id", ondelete="CASCADE"), nullable=False, index=True)
    bank = Column(String, nullable=False)  # HDFC, ICICI, SBI, Axis, Amazon Pay, etc.
    card_type = Column(String, nullable=False)  # Credit, Debit, All
    discount_type = Column(String, nullable=False)  # Percentage, Flat
    discount_value = Column(Float, nullable=False)
    min_purchase = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True)

    # Relationships
    product_link = relationship("ProductLink", back_populates="offers")

