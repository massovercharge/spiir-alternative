from pathlib import Path

path = Path("backend/app/reference_api.py")
content = path.read_text(encoding="utf-8")

# Change import
content = content.replace("from .bank_service import", "from .bank_service import")

# Mount scheduler
imports = "from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status\nfrom contextlib import asynccontextmanager\nfrom .scheduler import start_scheduler, shutdown_scheduler\n"
content = content.replace("from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status\n", imports)

lifespan = """@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()

def create_app() -> FastAPI:
    app = FastAPI(title="Spiir Alternative Reference API", version="0.1.0", lifespan=lifespan)
"""
content = content.replace("def create_app() -> FastAPI:\n    app = FastAPI(title=\"Spiir Alternative Reference API\", version=\"0.1.0\")\n", lifespan)

# Change routes
content = content.replace('"/api/bank/', '"/api/bank/')

path.write_text(content, encoding="utf-8")
