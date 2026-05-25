from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import data, favorites, health, inquiries, me, properties, requirements

app = FastAPI(title="Real Estate API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(me.router)
app.include_router(data.router)
app.include_router(properties.router)
app.include_router(requirements.router)
app.include_router(favorites.router)
app.include_router(inquiries.router)
