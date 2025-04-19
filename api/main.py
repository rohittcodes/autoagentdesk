from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from api.routes import logs, queries, credentials, ingest

app = FastAPI(
    title="Log Analysis AI API",
    description="API for real-time log analysis with AI",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(logs.router)
app.include_router(queries.router)
app.include_router(credentials.router)
app.include_router(ingest.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    with open("static/index.html") as f:
        return f.read()

@app.get("/health")
async def health_check():
    # add more sophisticated health checks here
    return {"status": "healthy"}