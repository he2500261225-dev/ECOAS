from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import (
    assets,
    auth,
    competitors,
    creative,
    dashboard,
    demo,
    diagnoses,
    products,
    skus,
    stores,
    tasks,
)
from .config import DATA_DIR
from .db import Base, engine
from .engine.worker import worker_pool
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed()
    worker_pool.start()
    try:
        yield
    finally:
        worker_pool.stop()


app = FastAPI(title="电商运营助手 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=str(DATA_DIR)), name="files")

app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(skus.router)
app.include_router(competitors.router)
app.include_router(diagnoses.router)
app.include_router(creative.router)
app.include_router(tasks.router)
app.include_router(assets.router)
app.include_router(dashboard.router)
app.include_router(demo.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
