"""
Integration tests for API key authentication.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import APIKey, User
from src.utils.auth import generate_api_key, hash_api_key


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        email="admin@test.com",
        username="testadmin",
        is_admin=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a regular user for testing."""
    user = User(
        email="user@test.com",
        username="testuser",
        is_admin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive user for testing."""
    user = User(
        email="inactive@test.com",
        username="inactiveuser",
        is_admin=False,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_api_key(db_session: AsyncSession, admin_user: User) -> tuple[str, APIKey]:
    """Create an API key for admin user."""
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10]

    api_key_obj = APIKey(
        user_id=admin_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Test Admin Key",
        is_active=True,
        rate_limit=1000,
    )
    db_session.add(api_key_obj)
    await db_session.commit()
    await db_session.refresh(api_key_obj)

    return api_key, api_key_obj


@pytest.fixture
async def user_api_key(db_session: AsyncSession, regular_user: User) -> tuple[str, APIKey]:
    """Create an API key for regular user."""
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10]

    api_key_obj = APIKey(
        user_id=regular_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Test User Key",
        is_active=True,
        rate_limit=100,
    )
    db_session.add(api_key_obj)
    await db_session.commit()
    await db_session.refresh(api_key_obj)

    return api_key, api_key_obj


@pytest.fixture
async def expired_api_key(db_session: AsyncSession, regular_user: User) -> tuple[str, APIKey]:
    """Create an expired API key."""
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10]

    api_key_obj = APIKey(
        user_id=regular_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Expired Key",
        is_active=True,
        rate_limit=100,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired yesterday
    )
    db_session.add(api_key_obj)
    await db_session.commit()
    await db_session.refresh(api_key_obj)

    return api_key, api_key_obj


@pytest.fixture
async def inactive_api_key(db_session: AsyncSession, regular_user: User) -> tuple[str, APIKey]:
    """Create an inactive API key."""
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10]

    api_key_obj = APIKey(
        user_id=regular_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Inactive Key",
        is_active=False,  # Inactive
        rate_limit=100,
    )
    db_session.add(api_key_obj)
    await db_session.commit()
    await db_session.refresh(api_key_obj)

    return api_key, api_key_obj


class TestHealthEndpoint:
    """Tests for public health endpoint."""

    def test_health_without_auth(self, test_client: TestClient):
        """Health endpoint should work without authentication."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert "database" in data


class TestAuthenticatedEndpoints:
    """Tests for endpoints requiring authentication."""

    def test_starlistings_without_auth(self, test_client: TestClient, seed_starlistings):
        """Starlistings endpoint should reject requests without auth."""
        response = test_client.get("/starlistings")
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_starlistings_with_valid_auth(
        self, test_client: TestClient, seed_starlistings, user_api_key
    ):
        """Starlistings endpoint should accept valid API key."""
        api_key, _ = user_api_key
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "starlistings" in data
        assert len(data["starlistings"]) > 0

    def test_starlistings_with_invalid_auth(self, test_client: TestClient, seed_starlistings):
        """Starlistings endpoint should reject invalid API key."""
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": "Bearer kb_invalid_key_1234567890"}
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_starlistings_with_expired_key(
        self, test_client: TestClient, seed_starlistings, expired_api_key
    ):
        """Starlistings endpoint should reject expired API key."""
        api_key, _ = expired_api_key
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_starlistings_with_inactive_key(
        self, test_client: TestClient, seed_starlistings, inactive_api_key
    ):
        """Starlistings endpoint should reject inactive API key."""
        api_key, _ = inactive_api_key
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()


class TestAdminEndpoints:
    """Tests for admin-only endpoints."""

    def test_create_user_without_auth(self, test_client: TestClient):
        """Admin endpoint should reject requests without auth."""
        response = test_client.post(
            "/admin/users",
            json={"email": "new@test.com", "username": "newuser", "is_admin": False}
        )
        assert response.status_code == 401

    def test_create_user_with_regular_user(
        self, test_client: TestClient, user_api_key
    ):
        """Admin endpoint should reject regular users."""
        api_key, _ = user_api_key
        response = test_client.post(
            "/admin/users",
            json={"email": "new@test.com", "username": "newuser", "is_admin": False},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_create_user_with_admin(
        self, test_client: TestClient, admin_api_key
    ):
        """Admin endpoint should accept admin users."""
        api_key, _ = admin_api_key
        response = test_client.post(
            "/admin/users",
            json={"email": "new@test.com", "username": "newuser", "is_admin": False},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@test.com"
        assert data["username"] == "newuser"

    def test_list_users_with_admin(
        self, test_client: TestClient, admin_api_key, regular_user
    ):
        """List users endpoint should work for admin."""
        api_key, _ = admin_api_key
        response = test_client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # admin + regular user

    def test_create_api_key_with_admin(
        self, test_client: TestClient, admin_api_key, regular_user
    ):
        """Create API key endpoint should work for admin."""
        api_key, _ = admin_api_key
        response = test_client.post(
            f"/admin/users/{regular_user.id}/keys",
            json={"name": "New Test Key", "rate_limit": 500},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Test Key"
        assert data["rate_limit"] == 500
        assert "key" in data  # Full key returned only once
        assert data["key"].startswith("kb_")


class TestAPIKeyLastUsed:
    """Tests for API key last_used_at tracking."""

    async def test_last_used_updated_on_request(
        self, test_client: TestClient, db_session: AsyncSession,
        seed_starlistings, user_api_key
    ):
        """API key last_used_at should be updated on each request."""
        api_key_str, api_key_obj = user_api_key

        # Record initial last_used_at (should be None)
        initial_last_used = api_key_obj.last_used_at

        # Make authenticated request
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key_str}"}
        )
        assert response.status_code == 200

        # Refresh the API key object from database
        await db_session.refresh(api_key_obj)

        # Verify last_used_at was updated
        assert api_key_obj.last_used_at is not None
        if initial_last_used:
            assert api_key_obj.last_used_at > initial_last_used


class TestInactiveUserAPIKey:
    """Tests for API keys belonging to inactive users."""

    async def test_inactive_user_key_rejected(
        self, test_client: TestClient, db_session: AsyncSession,
        seed_starlistings, inactive_user
    ):
        """API keys for inactive users should be rejected."""
        # Create API key for inactive user
        api_key = generate_api_key()
        key_hash = hash_api_key(api_key)
        key_prefix = api_key[:10]

        api_key_obj = APIKey(
            user_id=inactive_user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name="Inactive User Key",
            is_active=True,  # Key is active, but user is not
            rate_limit=100,
        )
        db_session.add(api_key_obj)
        await db_session.commit()

        # Try to use the key
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 403
        assert "User account is inactive" in response.json()["detail"]


class TestAuthorizationHeaderFormats:
    """Tests for different authorization header formats."""

    def test_missing_authorization_header(self, test_client: TestClient, seed_starlistings):
        """Request without Authorization header should be rejected."""
        response = test_client.get("/starlistings")
        assert response.status_code == 401

    def test_malformed_authorization_header(
        self, test_client: TestClient, seed_starlistings
    ):
        """Malformed Authorization header should be rejected."""
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401

    def test_correct_bearer_format(
        self, test_client: TestClient, seed_starlistings, user_api_key
    ):
        """Correct Bearer format should be accepted."""
        api_key, _ = user_api_key
        response = test_client.get(
            "/starlistings",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
