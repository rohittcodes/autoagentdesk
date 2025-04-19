from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from api.routes import logs, queries

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

@app.get("/")
async def root():
    return {"message": "Welcome to the Log Analysis AI API"}

@app.get("/health")
async def health_check():
    # add more sophisticated health checks here
    return {"status": "healthy"}