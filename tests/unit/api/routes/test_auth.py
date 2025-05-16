from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from openmanufacturing.api.dependencies import User as PydanticUser  # For /me endpoint response
from openmanufacturing.api.dependencies import get_current_active_user, get_session

# Assuming the main FastAPI app is in openmanufacturing.api.main
# Adjust the import path according to your actual app structure if it differs.
# The path to app would be from where `pytest` is run or how PYTHONPATH is set.
# For poetry, if tests are run from `openmanufacturing` dir, this should work.
from openmanufacturing.api.main import app
from openmanufacturing.core.database.models import User as DBUser
from openmanufacturing.core.security import get_password_hash


@pytest.fixture
def client(mock_db_session_override):  # Add override for get_session
    return TestClient(app)


# Mock database session fixture
@pytest.fixture
def mock_db_session_override(mock_db_session):  # Renamed to avoid direct use by client itself
    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=None)  # Default to user not found
    session.execute = AsyncMock()
    session.scalars = MagicMock()
    session.scalars.first = MagicMock(return_value=None)
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_active_user():
    user = PydanticUser(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        is_admin=False,
        scopes=["read:items"],
    )
    return user


@pytest.fixture
def mock_get_current_active_user_override(mock_active_user):  # Override for /me endpoint
    async def override_get_current_active_user():
        return mock_active_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield
    app.dependency_overrides.clear()


# --- Test Cases --- #


@pytest.mark.asyncio
async def test_login_for_access_token_success(client, mock_db_session):
    test_username = "testloginuser"
    test_password = "password123"
    hashed_password = get_password_hash(test_password)

    mock_user_db = DBUser(
        id=1,
        username=test_username,
        email="login@example.com",
        hashed_password=hashed_password,
        is_active=True,
        is_admin=False,
    )

    # Configure mock_db_session to return this user
    async def mock_execute_effect(_):
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_user_db
        return MagicMock(scalars=mock_scalars)

    mock_db_session.execute.side_effect = mock_execute_effect

    response = client.post(
        "/api/auth/token", data={"username": test_username, "password": test_password}
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["username"] == test_username
    assert "read:items" in token_data["scopes"]  # Example scope


@pytest.mark.asyncio
async def test_login_for_access_token_incorrect_password(client, mock_db_session):
    test_username = "testuser"
    hashed_password = get_password_hash("correctpassword")
    mock_user_db = DBUser(
        id=1,
        username=test_username,
        email="test@example.com",
        hashed_password=hashed_password,
        is_active=True,
    )

    async def mock_execute_effect(_):
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_user_db
        return MagicMock(scalars=mock_scalars)

    mock_db_session.execute.side_effect = mock_execute_effect

    response = client.post(
        "/api/auth/token", data={"username": test_username, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


@pytest.mark.asyncio
async def test_login_for_access_token_inactive_user(client, mock_db_session):
    test_username = "inactiveuser"
    test_password = "password123"
    hashed_password = get_password_hash(test_password)
    mock_user_db = DBUser(
        id=1,
        username=test_username,
        email="inactive@example.com",
        hashed_password=hashed_password,
        is_active=False,
    )

    async def mock_execute_effect(_):
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_user_db
        return MagicMock(scalars=mock_scalars)

    mock_db_session.execute.side_effect = mock_execute_effect

    response = client.post(
        "/api/auth/token", data={"username": test_username, "password": test_password}
    )
    assert response.status_code == 400  # As per auth.py logic for inactive user on login
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.asyncio
async def test_register_user_success(client, mock_db_session):
    # Ensure user does not exist initially
    mock_db_session.execute.side_effect = None  # Reset side effect
    mock_db_session.scalars().first.return_value = None

    user_data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepassword123",
        "full_name": "New User",
        "is_admin": False,
    }
    response = client.post("/api/auth/register", json=user_data)

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["username"] == user_data["username"]
    assert response_data["email"] == user_data["email"]
    assert response_data["full_name"] == user_data["full_name"]
    assert response_data["is_admin"] == user_data["is_admin"]
    assert response_data["is_active"] is True  # Default active
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_already_exists(client, mock_db_session):
    existing_username = "existinguser"
    # Simulate user already exists
    mock_existing_user = DBUser(
        id=2, username=existing_username, email="exists@example.com", hashed_password="somehash"
    )

    async def mock_execute_effect_exists(_):
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_existing_user
        return MagicMock(scalars=mock_scalars)

    mock_db_session.execute.side_effect = mock_execute_effect_exists

    user_data = {
        "username": existing_username,
        "email": "newemail@example.com",
        "password": "password123",
    }
    response = client.post("/api/auth/register", json=user_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already registered"


@pytest.mark.asyncio
async def test_read_users_me(client, mock_get_current_active_user_override, mock_active_user):
    # The mock_get_current_active_user_override fixture handles overriding the dependency
    # The mock_active_user provides the PydanticUser model instance
    response = client.get(
        "/api/auth/me"
    )  # No token needed as TestClient handles dependency overrides

    assert response.status_code == 200
    user_info = response.json()
    assert user_info["username"] == mock_active_user.username
    assert user_info["email"] == mock_active_user.email
    assert user_info["full_name"] == mock_active_user.full_name
    assert user_info["is_admin"] == mock_active_user.is_admin
    assert user_info["is_active"] == mock_active_user.is_active
    assert user_info["scopes"] == mock_active_user.scopes
