from itertools import product

from fastapi import FastAPI
from api.database import Base, engine
from api.routers import auth, users, sellers, products

api = FastAPI(title="Ecommerce Platform API", version="1.0.0")

api.include_router(auth.router)
api.include_router(users.router)
api.include_router(sellers.router)
api.include_router(products.router)

@api.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@api.get("/")
def root():
    return {"message": "Ecommerce backend is running"}