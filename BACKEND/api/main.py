import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.database import Base, engine
from api.routers import auth, users, sellers, products, admin, cart, orders, payments, inventory, coupons
from fastapi.staticfiles import StaticFiles
from api.routers import stores

api = FastAPI(title="Ecommerce Platform API", version="1.0.0")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@api.get("/")
def root():
    return {"message": "Ecommerce backend is running"}

api.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

api.include_router(auth.router)
api.include_router(users.router)
api.include_router(sellers.router)
api.include_router(products.router)
api.include_router(cart.router)
api.include_router(orders.router)
api.include_router(payments.router)
api.include_router(inventory.router)
api.include_router(coupons.router)
api.include_router(admin.router)
api.include_router(stores.router)


