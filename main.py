from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import logging

from admin_routes import router as admin_router
import models
from database import engine

app = FastAPI(title="License Server")

app.include_router(admin_router)

app.mount(
    "/admin-ui",
    StaticFiles(directory="static/admin", html=True),
    name="admin-ui",
)

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    logging.info("Database ready")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    return {"message": "License Server running"}
