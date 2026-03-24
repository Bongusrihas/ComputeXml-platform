from fastapi import FastAPI
from routes.routes import router
from dotenv import load_dotenv
import os

load_dotenv()

CPLUS_ENGINE_PATH = os.getenv("CPLUS_ENGINE_PATH")
app = FastAPI(title="Computex Python Orchestrator")

app.include_router(router, prefix="/api", tags=["Core"])


#uvicorn app.main:app --host 0.0.0.0 --port 8000
#for running




















