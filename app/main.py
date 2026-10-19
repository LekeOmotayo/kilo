"""Main FastAPI application factory and ASGI entrypoint for the TokenOps Gateway."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import logger, request_id_ctx, setup_logging, trace_id_ctx
from app.services.cache import semantic_cache
from app.services.tokenops import tokenops_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management for connection pools and graceful termination."""
    # Setup structured JSON logging
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} "
        f"[Embedding: {settings.EMBEDDING_PROVIDER}, Upstream: {settings.UPSTREAM_PROVIDER}]"
    )

    # Initialize Redis vector search connection and index
    if settings.CACHE_ENABLED:
        await semantic_cache.connect()

    yield

    # Clean up connection resources
    logger.info("Shutting down TokenOps Gateway. Closing Redis connections...")
    await semantic_cache.close()
    logger.info("Shutdown complete.")


def create_application() -> FastAPI:
    """Create and configure the production FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Enterprise LLM Semantic Caching & TokenOps Gateway. "
            "Delivers sub-millisecond semantic cache hits via Redis Vector Search, "
            "intelligent model-tiering routing, and comprehensive TokenOps cost tracking."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Distributed Tracing & Request ID Middleware
    @app.middleware("http")
    async def trace_and_timing_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        req_id = str(uuid.uuid4())
        trace_id_ctx.set(trace_id)
        request_id_ctx.set(req_id)

        t_start = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - t_start) * 1000.0
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Request-Id"] = req_id
            response.headers["X-Gateway-Time-Ms"] = f"{duration_ms:.2f}"
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000.0
            logger.error(
                f"Unhandled request error on {request.method} {request.url.path}: {exc}",
                exc_info=True,
                extra={"trace_id": trace_id},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal gateway processing failure.",
                        "type": "gateway_internal_error",
                        "trace_id": trace_id,
                    }
                },
                headers={
                    "X-Trace-Id": trace_id,
                    "X-Request-Id": req_id,
                    "X-Gateway-Time-Ms": f"{duration_ms:.2f}",
                },
            )

    # Mount static assets and serve interactive frontend dashboard
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        @app.get("/dashboard", include_in_schema=False)
        async def serve_dashboard():
            return FileResponse(str(static_dir / "index.html"))

    # Include API v1 router
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    # Register chat completions at root for standard OpenAI client compatibility
    from app.api.v1.endpoints import chat
    app.include_router(chat.router, prefix="", tags=["LLM Gateway (Root Alias)"])

    # Root Prometheus scraping endpoint
    @app.get("/metrics", tags=["Observability"])
    async def metrics_root():
        data = tokenops_service.export_prometheus_metrics()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    # Root health probe
    @app.get("/health", tags=["Health"])
    async def health_root():
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }

    return app


app = create_application()
