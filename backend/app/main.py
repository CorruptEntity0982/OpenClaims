"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import patients, documents, health
from app.services.graph_service import graph_service
import logging

logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url=None,  # Disable redoc
    openapi_url="/openapi.json",
    root_path="/api",  # Tell FastAPI it's behind a reverse proxy at /api
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    logger.info("Application starting up...")
    
    # Initialize Neo4j constraints
    logger.info("Ensuring Neo4j constraints are created...")
    try:
        graph_service.ensure_constraints()
        logger.info("Neo4j constraints initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j constraints: {str(e)}")
        # Don't fail startup if Neo4j is unavailable
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown"""
    logger.info("Application shutting down...")
    
    # Close Neo4j connection
    try:
        graph_service.close()
        logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error closing Neo4j connection: {str(e)}")
    
    logger.info("Application shutdown complete")


# Include routers
app.include_router(health.router)
app.include_router(patients.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    """Hello World endpoint"""
    return {"message": "Hello World from OpenClaims!"}
