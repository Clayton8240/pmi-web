import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.database import create_tables
from app.config import OUTPUT_FOLDER
from app.routers import cds, materiais, etiquetas, importacao, api


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs("assets", exist_ok=True)
    yield


app = FastAPI(title="PMI Etiquetas Web", version="2.0.0", lifespan=lifespan)

# Arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/etiquetas_geradas", StaticFiles(directory=OUTPUT_FOLDER), name="geradas")

# Routers
app.include_router(cds.router)
app.include_router(materiais.router)
app.include_router(etiquetas.router)
app.include_router(importacao.router)
app.include_router(api.router)


@app.get("/")
def root():
    return RedirectResponse("/etiquetas/gerar")
