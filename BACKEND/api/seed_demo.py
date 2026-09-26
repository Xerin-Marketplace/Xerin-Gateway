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
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from api.database import SessionLocal
from api.models import (
    Advertisement,
    Category,
    Inventory,
    Product,
    ProductImage,
    ProductStatus,
    Role,
    Seller,
    SellerStatus,
    Store,
    User,
    UserRole,
    UserStatus,
    Warehouse,
    WarehouseBin,
    WarehouseInventory,
)
from api.enums import WarehouseStatus
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
        # Match by email OR phone — a user sharing the demo phone with a
        # different email must not cause a unique-constraint crash.
        user = db.query(User).filter(
            (User.email == DEMO_SELLER_EMAIL) | (User.phone == "+255700000001")
        ).first()
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

        # --- warehouse + bins ---
        warehouse = db.query(Warehouse).filter(Warehouse.code == "DAR-01").first()
        if not warehouse:
            warehouse = Warehouse(
                name="Dar es Salaam Hub",
                code="DAR-01",
                country="Tanzania",
                region="Dar es Salaam",
                district="Ilala",
                ward="Kariakoo",
                street="Msimbazi St",
                total_capacity=5000,
                status=WarehouseStatus.active,
            )
            db.add(warehouse)
            db.flush()

        bins = db.query(WarehouseBin).filter(WarehouseBin.warehouse_id == warehouse.id).all()
        if not bins:
            bins = [
                WarehouseBin(warehouse_id=warehouse.id, aisle="A1", shelf="S1", bin=f"B{i}",
                             zone="general", capacity=100)
                for i in range(1, 5)
            ]
            db.add_all(bins)
            db.flush()

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
            db.add(WarehouseInventory(
                warehouse_id=warehouse.id,
                product_id=product.id,
                seller_id=seller.id,
                quantity=qty,
                reserved_quantity=0,
                available_quantity=qty,
                low_stock_threshold=5,
                warehouse_bin_id=random.choice(bins).id,
            ))
            created += 1

        db.commit()

        # --- advertisements (public slots) ---
        now = datetime.now(timezone.utc)
        seed_products = {
            p.slug: p for p in db.query(Product).filter(Product.is_active.is_(True)).all()
        }
        featured_slug = next(iter(seed_products), None)

        demo_ads = [
            dict(
                advertiser_name="Xerin Marketplace",
                title="This Week's Top Deals",
                description="Hand-picked products from verified sellers with protected checkout and tracked delivery.",
                image_url="/images/hero/headphone.png",
                alt_text="Featured headphones on sale at Xerin",
                target_url=f"/products/{featured_slug}" if featured_slug else "/shop-with-sidebar",
                cta_label="Shop Now",
                placement="hero_side_top",
                priority=10,
            ),
            dict(
                advertiser_name="Xerin Marketplace",
                title="New Seller Arrivals",
                description="Fresh stock from sellers near you — delivered and tracked.",
                image_url="/images/hero/Tshirtremove.png",
                alt_text="New fashion arrivals at Xerin",
                target_url="/shop-with-sidebar",
                cta_label="Explore",
                placement="hero_side_bottom",
                priority=5,
            ),
            dict(
                advertiser_name="Xerin Marketplace",
                title="Sell on Xerin",
                description="Open your store, reach thousands of buyers, and get paid through protected checkout.",
                image_url="/images/hero/hero-01.png",
                alt_text="Become a Xerin seller",
                target_url="/seller/register",
                cta_label="Start Selling",
                placement="homepage_banner",
                priority=5,
            ),
        ]

        ads_created = 0
        for spec in demo_ads:
            exists = db.query(Advertisement).filter(
                Advertisement.placement == spec["placement"],
                Advertisement.title == spec["title"],
            ).first()
            if exists:
                continue
            db.add(Advertisement(
                **spec,
                status="active",
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=60),
                billing_type="fixed",
                currency="TZS",
            ))
            ads_created += 1

        db.commit()
        print(f"Demo seed complete: {created} new products, {ads_created} ads, "
              f"seller login {DEMO_SELLER_EMAIL} / {DEMO_SELLER_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
