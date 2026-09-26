import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.routers import auth, lost, found, matches, search, dashboard, messages, admin, demo, recovery

app = FastAPI(
    title="FindBack AI",
    description=(
        "AI-powered Lost & Found platform. Report lost/found items, get "
        "transparent AI Match Score suggestions, and communicate safely "
        "in-app without exposing private contact details."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    init_db()


# Serve uploaded photos
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# --- Consistent error responses -------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Validation failed", "details": exc.errors()})


# --- Routers ----------------------------------------------------------------

app.include_router(auth.router)
app.include_router(lost.router)
app.include_router(found.router)
app.include_router(matches.router)          # POST /api/match
app.include_router(matches.matches_router)  # GET/PATCH /api/matches/*
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(messages.router)
app.include_router(admin.router)
app.include_router(demo.router)
app.include_router(recovery.router)


@app.get("/")
def root():
    return {
        "name": "FindBack AI backend",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
