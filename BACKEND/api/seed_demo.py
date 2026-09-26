"""Seed demo marketplace data for development/testing environments.

Creates a demo seller, store, categories and products with inventory so the
storefront has real content to render. Idempotent — safe to run repeatedly.

Usage:
    python -m api.seed_demo
"""

from __future__ import annotations

import random
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import func

from api.database import SessionLocal
from api.models import (
    Category,
    Inventory,
    Product,
    ProductImage,
    Role,
    Seller,
    SellerStatus,
    Store,
    User,
    UserRole,
    UserStatus,
)
from api.enums import ProductStatus
from api.security import hash_password

DEMO_SELLER_EMAIL = "seller@xerin.dev"
DEMO_SELLER_PASSWORD = "Seller2026!Demo"

CATEGORIES = [
    ("Electronics", "electronics"),
    ("Phones & Tablets", "phones-tablets"),
    ("Fashion", "fashion"),
    ("Home & Kitchen", "home-kitchen"),
    ("Beauty & Personal Care", "beauty-personal-care"),
]

PRODUCTS = [
    # (name, price_tzs, sale_price_tzs, category_slug, description)
    ("Samsung Galaxy A15 128GB", 385000, 349000, "phones-tablets",
     "6.5\" display, 128GB storage, 5000mAh battery, dual SIM."),
    ("iPhone 13 128GB", 1450000, 1380000, "phones-tablets",
     "A15 Bionic chip, dual camera system, Super Retina XDR display."),
    ("HP EliteBook 840 G8", 1250000, None, "electronics",
     "Intel Core i5, 16GB RAM, 512GB SSD, 14\" FHD display."),
    ("Sony WH-1000XM4 Headphones", 780000, 695000, "electronics",
     "Industry-leading noise cancellation, 30-hour battery life."),
    ("Anker PowerBank 20000mAh", 85000, None, "electronics",
     "High-capacity portable charger, fast charging support."),
    ("Men's Casual T-Shirt", 25000, 18900, "fashion",
     "100% cotton crew neck t-shirt, available in multiple sizes."),
    ("Women's Kitenge Dress", 65000, 52000, "fashion",
     "Authentic African kitenge print dress, handmade in Tanzania."),
    ("Leather Wallet", 35000, None, "fashion",
     "Genuine leather bifold wallet with card slots."),
    ("Non-Stick Cookware Set 10pc", 145000, 119000, "home-kitchen",
     "10-piece non-stick pots and pans set, induction compatible."),
    ("Electric Kettle 1.8L", 45000, None, "home-kitchen",
     "Fast-boil electric kettle, auto shut-off, stainless steel."),
    ("Shea Butter Body Lotion 400ml", 28000, 22000, "beauty-personal-care",
     "Deep moisturizing lotion with natural shea butter."),
    ("Argan Oil Hair Serum 100ml", 32000, None, "beauty-personal-care",
     "Frizz control and shine serum with pure argan oil."),
]


def _slug_exists(db, model, slug: str) -> bool:
    return db.query(model).filter(model.slug == slug).first() is not None


def seed_demo() -> None:
    db = SessionLocal()
    try:
        # --- demo seller user ---
        user = db.query(User).filter(User.email == DEMO_SELLER_EMAIL).first()
        if not user:
            user = User(
                first_name="Demo",
                last_name="Seller",
                email=DEMO_SELLER_EMAIL,
                phone="+255700000001",
                password_hash=hash_password(DEMO_SELLER_PASSWORD),
                status=UserStatus.active,
                is_verified=True,
            )
            db.add(user)
            db.flush()

        seller_role = db.query(Role).filter(Role.name == "seller").first()
        if seller_role is None:
            seller_role = Role(name="seller", description="Marketplace seller")
            db.add(seller_role)
            db.flush()
        if not db.query(UserRole).filter(
            UserRole.user_id == user.id, UserRole.role_id == seller_role.id
        ).first():
            db.add(UserRole(user_id=user.id, role_id=seller_role.id))

        seller = db.query(Seller).filter(Seller.user_id == user.id).first()
        if not seller:
            seller = Seller(
                user_id=user.id,
                business_name="Xerin Demo Store",
                contact_email=DEMO_SELLER_EMAIL,
                contact_phone="+255700000001",
                status=SellerStatus.approved,
                agreement_accepted=True,
                approved_at=datetime.now(timezone.utc),
            )
            db.add(seller)
            db.flush()

        # --- store ---
        if not _slug_exists(db, Store, "xerin-demo-store"):
            db.add(Store(
                seller_id=seller.id,
                store_name="Xerin Demo Store",
                slug="xerin-demo-store",
                description="Demo storefront with sample products.",
                country="Tanzania",
                region="Dar es Salaam",
                theme_color="#F97316",
                secondary_color="#ffffff",
            ))

        # --- categories ---
        category_ids: dict[str, uuid.UUID] = {}
        for name, slug in CATEGORIES:
            cat = db.query(Category).filter(Category.slug == slug).first()
            if not cat:
                cat = Category(name=name, slug=slug)
                db.add(cat)
                db.flush()
            category_ids[slug] = cat.id

        # --- products + inventory ---
        created = 0
        for name, price, sale_price, cat_slug, desc in PRODUCTS:
            slug = name.lower().replace(" ", "-").replace('"', "")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            if _slug_exists(db, Product, slug):
                continue
            product = Product(
                seller_id=seller.id,
                category_id=category_ids[cat_slug],
                sku=f"XER-{uuid.uuid4().hex[:8].upper()}",
                name=name,
                slug=slug,
                description=desc,
                price=Decimal(str(price)),
                sale_price=Decimal(str(sale_price)) if sale_price else None,
                currency="TZS",
                status=ProductStatus.approved,
                is_active=True,
                approved_at=datetime.now(timezone.utc),
            )
            db.add(product)
            db.flush()

            qty = random.randint(10, 80)
            db.add(Inventory(
                product_id=product.id,
                quantity=qty,
                reserved_quantity=0,
                available_quantity=qty,
                low_stock_threshold=5,
            ))
            created += 1

        db.commit()
        print(f"Demo seed complete: {created} new products, "
              f"seller login {DEMO_SELLER_EMAIL} / {DEMO_SELLER_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
