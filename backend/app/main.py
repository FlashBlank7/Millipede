from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.customer import auth as customer_auth
from app.api.customer import projects as customer_projects
from app.api.customer import runcard as customer_runcard
from app.api.customer import uploads as customer_uploads
from app.api.engineer import projects as engineer_projects
from app.api.engineer import review as engineer_review
from app.api.ws import runcard as ws_runcard
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Millipede API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer_auth.router, prefix="/api/v1")
app.include_router(customer_projects.router, prefix="/api/v1")
app.include_router(customer_runcard.router, prefix="/api/v1")
app.include_router(customer_uploads.router, prefix="/api/v1")
app.include_router(engineer_projects.router, prefix="/api/v1")
app.include_router(engineer_review.router, prefix="/api/v1")
app.include_router(ws_runcard.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
