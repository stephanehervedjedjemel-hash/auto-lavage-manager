from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.tenants import router as tenants_router
from app.bootstrap import create_tables
@asynccontextmanager
async def lifespan(_:FastAPI):
    if settings.app_env=="development": create_tables()
    yield
app=FastAPI(title="AUTO LAVAGE MANAGER API",version="0.2.0",
  description="API SaaS multi-entreprises et multi-stations de lavage automobile.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,
  allow_methods=["GET","POST","PUT","PATCH","DELETE"],allow_headers=["Authorization","Content-Type"])
app.include_router(tenants_router,prefix="/api/v1",tags=["Entreprises, stations et authentification"])
@app.get("/health",tags=["Système"])
def health(): return {"status":"ok","application":"AUTO LAVAGE MANAGER","version":"0.2.0"}
@app.get("/api/v1",tags=["Système"])
def api_root(): return {"message":"Bienvenue dans AUTO LAVAGE MANAGER","currency":"XOF","language":"fr"}
