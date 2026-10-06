"""Seed a demo seller with a full storefront catalogue for the live site.

Creates one approved demo seller ("Xerin Flagship Store"), ~200 products
spread across every existing category (TZS 5,000–300,000, ~35% on sale),
inventory stock, a demo customer with delivered orders (so sold-counts are
real), and approved reviews (so ratings show).

Idempotent: safe to re-run — it skips products whose DEMO-* SKU exists.

Usage (on the server):
    cd /var/Xerin-Gateway/BACKEND
    .venv/bin/python -m api.seed_demo_store
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from api.database import SessionLocal
from api.models import (
    Category,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductImage,
    ProductReview,
    ProductStatus,
    ReviewStatus,
    Role,
    Seller,
    SellerStatus,
    Store,
    User,
    UserRole,
    UserStatus,
)
from api.security import hash_password

DEMO_SELLER_EMAIL = "demo.seller@xerinmart.com"
DEMO_CUSTOMER_EMAIL = "demo.customer@xerinmart.com"
DEMO_PASSWORD = "Demo2026!Store"
PRODUCT_COUNT = 200
ORDER_COUNT = 35
SITE = "https://xerinmart.com"

random.seed(42)

# ---------------------------------------------------------------- images

IMAGE_POOL = [
    f"{SITE}/images/hero/headphone.png",
    f"{SITE}/images/hero/head.png",
    f"{SITE}/images/hero/headphon.png",
    f"{SITE}/images/hero/Tshirt.png",
    f"{SITE}/images/hero/hero-01.png",
    f"{SITE}/images/hero/hero-02.png",
    f"{SITE}/images/hero/hero-03.png",
] + [
    f"{SITE}/images/products/product-{n}-{size}-{v}.png"
    for n in range(1, 9)
    for size in ("bg", "sm")
    for v in (1, 2)
]

# ------------------------------------------------- per-category name pools
# Keyed on a substring of the category slug; falls back to GENERIC.

CATEGORY_ITEMS = {
    "appliance": [
        "Electric Kettle 1.8L", "Steam Iron 2200W", "Blender 2-Speed 1.5L",
        "Rice Cooker 2.2L", "Microwave Oven 20L", "Stand Fan 16 Inch",
        "Vacuum Cleaner 1200W", "Air Fryer 4.5L", "Coffee Maker 12-Cup",
        "Electric Grill Plate", "Water Dispenser Hot & Cold", "Toaster 2-Slice",
        "Hand Mixer 5-Speed", "Pressure Cooker 6L", "Juice Extractor 800W",
    ],
    "baby": [
        "Baby Diapers Pack 64pcs", "Baby Stroller Foldable", "Baby Carrier Ergonomic",
        "Baby Feeding Bottle 250ml Set", "Baby Blanket Soft Fleece",
        "Baby Walker with Music", "Baby Wipes 80pcs Pack", "Baby Crib Wooden",
        "Baby Bath Tub Anti-Slip", "Baby Clothes Set 5pc", "Pacifier Set BPA-Free",
        "Baby Monitor Audio", "Baby High Chair Adjustable", "Teething Toy Set",
        "Baby Shampoo Gentle 500ml",
    ],
    "bag": [
        "Leather Handbag Ladies", "Laptop Backpack 15.6\"", "Travel Duffel Bag 50L",
        "School Backpack Kids", "Crossbody Sling Bag", "Wallet Genuine Leather",
        "Luggage Suitcase 24\"", "Waist Bag Sport", "Clutch Purse Evening",
        "Tote Bag Canvas", "Camera Bag Padded", "Gym Bag with Shoe Pocket",
        "Messenger Bag Office", "Drawstring Bag Casual", "Briefcase Executive",
    ],
    "beauty": [
        "Shea Butter Body Lotion 400ml", "Argan Oil Hair Serum 100ml",
        "Facial Cleanser Vitamin C", "Lipstick Matte Set 6pc",
        "Perfume Floral 100ml", "Body Scrub Coffee 250g", "Sunscreen SPF50 150ml",
        "Hair Straightener Ceramic", "Makeup Brush Set 12pc", "Nail Polish Kit 10pc",
        "Face Mask Clay Detox", "Beard Oil Sandalwood 50ml", "Eye Shadow Palette 35",
        "Moisturizer Hyaluronic 50ml", "Braiding Hair Extension 24\"",
    ],
    "electronic": [
        "Bluetooth Speaker Portable", "Wireless Earbuds TWS Pro",
        "Smart TV 43 Inch FHD", "LED Monitor 24 Inch", "Gaming Mouse RGB",
        "Mechanical Keyboard", "Power Bank 20000mAh", "USB-C Hub 7-in-1",
        "Webcam HD 1080p", "Portable SSD 512GB", "Smartwatch Fitness Tracker",
        "WiFi Router Dual-Band", "TV Wall Mount 32-55\"", "Extension Cable 6-Way",
        "Drone Camera 4K",
    ],
    "phone": [
        "Smartphone 128GB Dual SIM", "Phone Case Shockproof", "Tempered Glass 9H",
        "Fast Charger 33W Type-C", "Car Phone Holder Magnetic", "Earphones Wired 3.5mm",
        "Tablet 10.1 Inch 64GB", "Phone Ring Holder", "OTG Cable USB-C",
        "Wireless Charger Pad 15W", "Phone Tripod Stand", "Screen Protector Pack",
        "Power Bank Slim 10000mAh", "Charging Cable Braided 2m", "Selfie Stick Bluetooth",
    ],
    "fashion": [
        "Men's Casual T-Shirt Cotton", "Women's Kitenge Dress", "Slim Fit Jeans Men",
        "Polo Shirt Classic", "Hoodie Unisex Fleece", "Ankara Print Skirt",
        "Formal Shirt Long Sleeve", "Maxi Dress Summer", "Denim Jacket Vintage",
        "Chino Trousers Stretch", "Blazer Slim Fit", "Graphic Tee Streetwear",
        "Cargo Pants Utility", "Sundress Floral", "Tracksuit Set 2pc",
    ],
    "shoe": [
        "Running Shoes Lightweight", "Leather Oxford Shoes", "Canvas Sneakers Casual",
        "Ladies Heels Classic", "Sports Sandals Outdoor", "Boots Ankle Leather",
        "Slides Comfort Fit", "School Shoes Black", "Basketball Shoes High-Top",
        "Loafers Slip-On", "Flip Flops Beach", "Safety Boots Steel-Toe",
        "Wedges Platform Ladies", "Trainers Breathable Mesh", "Baby Shoes Soft Sole",
    ],
    "home": [
        "Non-Stick Cookware Set 10pc", "Bed Sheet Set Cotton 6pc", "Curtain Blackout 2pc",
        "Throw Pillow Covers 4pc", "Wall Art Canvas 3-Panel", "Area Rug 160x230",
        "Storage Organizer 6-Tier", "Kitchen Knife Set 8pc", "Dinner Set 24pc Ceramic",
        "Water Bottle Insulated 1L", "Laundry Basket Foldable", "Mirror Wall Round 60cm",
        "Duvet Microfiber Queen", "Towel Set Egyptian Cotton", "Coat Rack Standing",
    ],
    "kitchen": [
        "Gas Cooker 4-Burner", "Deep Fryer Electric 3L", "Cutting Board Bamboo Set",
        "Spice Rack Rotating 16-Jar", "Food Storage Containers 10pc", "Kettle Whistling 3L",
        "Baking Tray Set Non-Stick", "Utensil Set Silicone 12pc", "Chopper Manual Pull",
        "Thermos Flask 2L", "Dish Rack 2-Tier", "Cooking Pot Set Granite 5pc",
        "Measuring Cups Set", "Oil Dispenser Glass 500ml", "Apron Chef Adjustable",
    ],
    "sport": [
        "Football Size 5 Official", "Yoga Mat Anti-Slip 6mm", "Dumbbell Set 20kg",
        "Skipping Rope Speed", "Resistance Bands Set 5pc", "Gym Gloves Padded",
        "Water Bottle Sport 750ml", "Basketball Outdoor Size 7", "Badminton Racket Pair",
        "Fitness Tracker Band", "Swim Goggles Anti-Fog", "Camping Tent 4-Person",
        "Bicycle Helmet Adjustable", "Boxing Gloves 12oz", "Fishing Rod Combo",
    ],
    "health": [
        "Vitamin C Tablets 1000mg", "Blood Pressure Monitor Digital", "Thermometer Infrared",
        "First Aid Kit Complete", "Hand Sanitizer 500ml", "Face Mask KN95 Pack 20",
        "Multivitamin Gummies 60pc", "Glucose Monitor Kit", "Massage Gun Deep Tissue",
        "Heating Pad Electric", "Pill Organizer Weekly", "Weighing Scale Digital",
        "Nebulizer Machine", "Wrist Support Brace", "Herbal Tea Detox 30 Bags",
    ],
    "automotiv": [
        "Car Phone Mount Dashboard", "Car Seat Covers Universal", "Jump Starter 12000mAh",
        "Car Vacuum Cleaner 12V", "Tire Inflator Portable", "Dash Cam Full HD",
        "Car Wash Kit 8pc", "Steering Wheel Cover Leather", "Car Charger Dual USB",
        "LED Headlight Bulbs H4", "Car Air Freshener Set", "Roof Cargo Box 400L",
        "OBD2 Scanner Bluetooth", "Wiper Blades Set", "Car Battery Charger Smart",
    ],
    "comput": [
        "Laptop Core i5 8GB 256GB", "Wireless Mouse Silent", "Laptop Stand Aluminum",
        "USB Flash Drive 128GB", "External HDD 1TB", "HDMI Cable 4K 2m",
        "Laptop Sleeve 14 Inch", "Keyboard Wireless Slim", "Mouse Pad XXL Gaming",
        "USB Docking Station", "RAM DDR4 8GB 3200", "CPU Cooler RGB",
        "Monitor Arm Mount", "Webcam Privacy Cover", "Cable Management Kit",
    ],
    "grocer": [
        "Rice Premium 5kg", "Cooking Oil Sunflower 3L", "Sugar White 2kg",
        "Wheat Flour 2kg", "Tea Leaves Premium 250g", "Coffee Beans Arabica 500g",
        "Honey Pure 1kg", "Pasta Spaghetti 500g x4", "Peanut Butter Crunchy 800g",
        "Maize Flour 5kg", "Beans Red Kidney 1kg", "Spice Mix Pilau 100g",
        "Powdered Milk 900g", "Coconut Oil Virgin 500ml", "Cashew Nuts Roasted 500g",
    ],
    "toy": [
        "Building Blocks Set 500pc", "RC Car Remote Control", "Doll House Furniture",
        "Puzzle 1000pc Landscape", "Action Figure Superhero", "Board Game Family",
        "Kids Scooter 3-Wheel", "Plush Teddy Bear 60cm", "Educational Tablet Kids",
        "Play Dough Set 24 Colors", "Water Gun Super Soaker", "Train Set Electric",
        "Drawing Board Magnetic", "Drone Mini Kids", "Bubble Machine Automatic",
    ],
    "jewel": [
        "Gold-Plated Necklace", "Silver Bracelet Charm", "Stud Earrings Crystal",
        "Watch Men Chronograph", "Watch Ladies Minimalist", "Ring Set Stainless 5pc",
        "Anklet Beaded Handmade", "Cufflinks Silver Pair", "Brooch Vintage Flower",
        "Waist Beads African Set", "Pendant Zirconia Heart", "Bangle Set Gold-Tone 6pc",
        "Ear Cuff Non-Pierced", "Tie Clip Classic", "Bracelet Leather Braided",
    ],
    "book": [
        "English-Swahili Dictionary", "Mathematics Textbook Form 4", "Business Startup Guide",
        "Children Story Book Set", "Notebook A5 Hardcover 3pc", "Bible Kiswahili",
        "Cookbook East African", "Self-Help Bestseller", "Atlas World Updated",
        "Coloring Book Kids 64pg", "Exam Revision Guide KCSE", "Novel African Classic",
        "Planner 2027 Weekly", "Sketchbook A4 Spiral", "Physics Practical Manual",
    ],
    "furniture": [
        "Office Chair Ergonomic", "Study Desk Wooden 120cm", "Bookshelf 5-Tier",
        "Sofa Set 3-Seater Fabric", "Coffee Table Modern", "TV Stand Entertainment",
        "Wardrobe 3-Door Mirror", "Dining Table Set 4-Chair", "Bed Frame Queen Size",
        "Mattress Orthopedic 6x6", "Shoe Rack 4-Tier", "Bar Stool Adjustable",
        "Folding Table Portable", "Nightstand with Drawer", "Recliner Chair Leather",
    ],
}

GENERIC_ITEMS = [
    "Premium {cat} Item Deluxe", "Classic {cat} Essential", "Pro {cat} Edition",
    "Smart {cat} Starter Pack", "Elite {cat} Bundle", "Eco {cat} Choice",
    "Compact {cat} Mini", "Luxury {cat} Series", "Everyday {cat} Basic",
    "Advanced {cat} Kit", "Travel {cat} Companion", "Modern {cat} Design",
    "Value {cat} Pack", "Signature {cat} Collection", "Ultra {cat} Pro",
]

ADJECTIVES = ["Premium", "Classic", "Smart", "Eco", "Deluxe", "Compact", "Pro", "Ultra"]

REVIEW_COMMENTS = [
    "Great quality for the price, highly recommended!",
    "Fast delivery and exactly as described.",
    "Good product, works perfectly.",
    "Value for money. Will buy again.",
    "Excellent! Exceeded my expectations.",
    "Solid build quality, very satisfied.",
    "Amazing product, my family loves it.",
    "Perfect fit and finish. Asante Xerin!",
    "Very good quality, delivery was quick.",
    "Does the job well, no complaints.",
]

REVIEW_TITLES = [
    "Great product", "Very satisfied", "Good value", "Excellent quality",
    "Recommended", "Happy customer", "Worth it", "Impressive",
]


def _items_for(slug: str, name: str) -> list[str]:
    for key, items in CATEGORY_ITEMS.items():
        if key in slug:
            return items
    cat_word = name.split("&")[0].split(" ")[0].strip()
    return [tpl.format(cat=cat_word) for tpl in GENERIC_ITEMS]


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def seed() -> None:
    db = SessionLocal()
    try:
        # ------------------------------------------------ seller + store
        user = db.query(User).filter(User.email == DEMO_SELLER_EMAIL).first()
        if not user:
            user = User(
                first_name="Xerin", last_name="Flagship",
                email=DEMO_SELLER_EMAIL, phone="+255713000001",
                password_hash=hash_password(DEMO_PASSWORD),
                status=UserStatus.active, is_verified=True,
            )
            db.add(user)
            db.flush()

        role = db.query(Role).filter(Role.name == "seller").first()
        if role and not db.query(UserRole).filter(
            UserRole.user_id == user.id, UserRole.role_id == role.id
        ).first():
            db.add(UserRole(user_id=user.id, role_id=role.id))

        seller = db.query(Seller).filter(Seller.user_id == user.id).first()
        if not seller:
            seller = Seller(
                user_id=user.id,
                business_name="Xerin Flagship Store",
                contact_email=DEMO_SELLER_EMAIL,
                contact_phone="+255713000001",
                status=SellerStatus.approved,
                agreement_accepted=True,
                approved_at=datetime.now(timezone.utc),
            )
            db.add(seller)
            db.flush()

        if not db.query(Store).filter(Store.slug == "xerin-flagship-store").first():
            db.add(Store(
                seller_id=seller.id,
                store_name="Xerin Flagship Store",
                slug="xerin-flagship-store",
                description="Official demo storefront — quality products at great prices.",
                country="Tanzania",
                region="Dar es Salaam",
                theme_color="#F97316",
                secondary_color="#ffffff",
            ))

        customer = db.query(User).filter(User.email == DEMO_CUSTOMER_EMAIL).first()
        if not customer:
            customer = User(
                first_name="Demo", last_name="Customer",
                email=DEMO_CUSTOMER_EMAIL, phone="+255713000002",
                password_hash=hash_password(DEMO_PASSWORD),
                status=UserStatus.active, is_verified=True,
            )
            db.add(customer)
            db.flush()

        # ------------------------------------------------ categories
        categories = db.query(Category).order_by(Category.name.asc()).all()
        if not categories:
            print("No categories found — create categories in admin first.")
            return

        # Leaf categories preferred (children over parents) so the two-pane
        # categories screen shows products in subcategory grids.
        parents_with_children = {c.parent_id for c in categories if c.parent_id}
        leaves = [c for c in categories if c.id not in parents_with_children]
        assignable = leaves or categories

        existing = (
            db.query(Product.id)
            .filter(Product.seller_id == seller.id, Product.sku.like("DEMO-%"))
            .count()
        )
        if existing >= PRODUCT_COUNT:
            print(f"Already seeded ({existing} DEMO products exist). Nothing to do.")
            return

        # ------------------------------------------------ products
        now = datetime.now(timezone.utc)
        created_products: list[Product] = []
        per_cat = max(1, PRODUCT_COUNT // len(assignable)) + 2
        sku_seq = existing + 1
        made = 0

        for cat in assignable:
            if made >= PRODUCT_COUNT:
                break
            items = _items_for(cat.slug, cat.name)
            for i in range(per_cat):
                if made >= PRODUCT_COUNT:
                    break
                base = items[i % len(items)]
                suffix = f"{random.choice(ADJECTIVES)} #{sku_seq}" if i >= len(items) else ""
                name = f"{base} {suffix}".strip()

                slug = (
                    name.lower()
                    .replace("&", "and").replace('"', "").replace("'", "")
                    .replace("  ", " ").replace(" ", "-").replace("/", "-")
                    + f"-{uuid.uuid4().hex[:6]}"
                )
                sku = f"DEMO-{sku_seq:05d}"
                sku_seq += 1

                price = Decimal(random.randrange(50, 3000)) * 100  # 5,000–300,000
                sale_price = None
                if random.random() < 0.35:
                    sale_price = (price * Decimal(random.randrange(60, 90)) / 100).quantize(Decimal("1"))

                product = Product(
                    seller_id=seller.id,
                    category_id=cat.id,
                    sku=sku,
                    name=name,
                    slug=slug,
                    description=(
                        f"{name} — quality-assured {cat.name.lower()} product from "
                        f"Xerin Flagship Store. Genuine, well-packaged, delivered "
                        f"fast anywhere in Tanzania."
                    ),
                    price=_money(price),
                    sale_price=_money(sale_price) if sale_price else None,
                    currency="TZS",
                    status=ProductStatus.approved,
                    is_active=True,
                    submitted_at=now - timedelta(days=random.randint(30, 120)),
                    approved_at=now - timedelta(days=random.randint(20, 100)),
                )
                db.add(product)
                db.flush()

                img_a = random.choice(IMAGE_POOL)
                img_b = random.choice(IMAGE_POOL)
                db.add(ProductImage(
                    product_id=product.id, image_url=img_a,
                    display_order=0, is_primary=True, alt_text=name,
                ))
                if img_b != img_a:
                    db.add(ProductImage(
                        product_id=product.id, image_url=img_b,
                        display_order=1, is_primary=False, alt_text=name,
                    ))

                qty = random.randint(20, 250)
                db.add(Inventory(
                    product_id=product.id, variant_id=None,
                    quantity=qty, reserved_quantity=0, available_quantity=qty,
                ))

                created_products.append(product)
                made += 1

        db.flush()
        print(f"Created {len(created_products)} products across {len(assignable)} categories.")

        # ------------------------------------------------ demo orders → sold counts
        order_items_all: list[tuple[OrderItem, Product]] = []
        for n in range(ORDER_COUNT):
            picks = random.sample(created_products, k=min(random.randint(2, 4), len(created_products)))
            order = Order(
                order_number=f"DEMO-ORD-{n + 1:04d}",
                user_id=customer.id,
                status=OrderStatus.delivered,
                currency="TZS",
                created_at=now - timedelta(days=random.randint(1, 60)),
            )
            db.add(order)
            db.flush()

            subtotal = Decimal("0")
            for p in picks:
                qty = random.randint(1, 4)
                unit = _money(p.sale_price or p.price)
                line_total = unit * qty
                item = OrderItem(
                    order_id=order.id,
                    product_id=p.id,
                    seller_id=seller.id,
                    product_name=p.name,
                    quantity=qty,
                    unit_price=unit,
                    total_price=_money(line_total),
                )
                db.add(item)
                db.flush()
                order_items_all.append((item, p))
                subtotal += line_total

            order.subtotal = _money(subtotal)
            order.total = _money(subtotal)

        # ------------------------------------------------ reviews → ratings
        reviews = 0
        for item, p in order_items_all:
            if random.random() > 0.45:
                continue
            db.add(ProductReview(
                product_id=p.id,
                order_item_id=item.id,
                customer_id=customer.id,
                seller_id=seller.id,
                rating=random.choice([3, 4, 4, 4, 5, 5, 5, 5]),
                title=random.choice(REVIEW_TITLES),
                comment=random.choice(REVIEW_COMMENTS),
                verified_purchase=True,
                status=ReviewStatus.approved,
                created_at=now - timedelta(days=random.randint(1, 45)),
            ))
            reviews += 1

        db.commit()
        print(
            f"Done: seller '{DEMO_SELLER_EMAIL}' ({DEMO_PASSWORD}), "
            f"{len(created_products)} products, {ORDER_COUNT} orders, {reviews} reviews."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
