"""Pytest fixtures and configuration for the Gateway test suite."""

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
import httpx

from app.core.config import settings
from app.main import app
from app.services.cache import semantic_cache


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Ensure test settings are locked to safe offline defaults."""
    settings.EMBEDDING_PROVIDER = "deterministic"
    settings.UPSTREAM_PROVIDER = "mock"
    settings.CACHE_ENABLED = True
    settings.SIMILARITY_THRESHOLD = 0.88


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an asynchronous HTTP client bound to the FastAPI ASGI app."""
    # Handle ASGITransport for modern httpx versions
    try:
        from httpx import ASGITransport
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    except (ImportError, TypeError):
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            yield client


@pytest_asyncio.fixture(autouse=True)
async def clean_cache_state():
    """Purge cache state before and after each test for deterministic test isolation."""
    await semantic_cache.purge()
    yield
    await semantic_cache.purge()
