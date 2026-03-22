"""
Test configuration and fixtures
===============================
Shared fixtures and configuration for all tests
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

import admin.dashboard as dashboard
from db.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create in-memory SQLite engine for testing."""
    # Use SQLite in-memory database for fast, isolated tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(engine):
    """Create async session for each test function."""
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
        # Rollback any changes after test
        try:
            await session.rollback()
        except SQLAlchemyError:
            pass


@pytest_asyncio.fixture(scope="function")
async def api_client(engine, monkeypatch):
    """API client bound to an isolated in-memory database."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(dashboard, "SESSION_FACTORY", session_factory)

    transport = ASGITransport(app=dashboard.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory


@pytest_asyncio.fixture(scope="function")
async def mock_bot(mocker):
    """Mock aiogram Bot instance."""
    mock_bot = mocker.AsyncMock()
    mock_bot.send_message = mocker.AsyncMock()
    return mock_bot


@pytest_asyncio.fixture(scope="function")
async def mock_connector_manager(mocker):
    """Mock ConnectorManager instance."""
    mock_manager = mocker.AsyncMock()
    mock_manager.scrape = mocker.AsyncMock()
    mock_manager.detect_store_type = mocker.AsyncMock(return_value="amazon")
    return mock_manager


@pytest_asyncio.fixture(scope="function")
async def mock_httpx_client(mocker):
    """Mock httpx.AsyncClient for HTTP requests."""
    mock_client = mocker.AsyncMock()
    mock_response = mocker.AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Test</body></html>"
    mock_client.get = mocker.AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
    return mock_client