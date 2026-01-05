"""
API Authentication Module
Supports API Key and JWT authentication for the Medication Validation Engine
"""
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# API Key configuration
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEY_QUERY = APIKeyQuery(name="api_key", auto_error=False)
BEARER_SCHEME = HTTPBearer(auto_error=False)

# Environment-based configuration
MASTER_API_KEY = os.getenv("MASTER_API_KEY", "hf-med-api-2026-master-key")
JWT_SECRET = os.getenv("JWT_SECRET", "healthflow-medication-engine-jwt-secret-2026")
API_KEY_PREFIX = "hf-med-"

# In-memory API key store (in production, use Redis or database)
api_keys_store: Dict[str, Dict[str, Any]] = {
    # Default keys for different access levels
    "hf-med-healthflow-prod": {
        "name": "HealthFlow Production",
        "access_level": "full",
        "rate_limit": 10000,
        "created_at": datetime.now().isoformat(),
        "active": True
    },
    "hf-med-pharmacy-pilot": {
        "name": "Pilot Pharmacy Integration",
        "access_level": "standard",
        "rate_limit": 1000,
        "created_at": datetime.now().isoformat(),
        "active": True
    },
    "hf-med-demo-readonly": {
        "name": "Demo Read-Only Access",
        "access_level": "readonly",
        "rate_limit": 100,
        "created_at": datetime.now().isoformat(),
        "active": True
    }
}


class APIKeyInfo(BaseModel):
    """API Key information model"""
    key: str
    name: str
    access_level: str
    rate_limit: int
    created_at: str
    active: bool


class AuthResult(BaseModel):
    """Authentication result"""
    authenticated: bool
    api_key: Optional[str] = None
    access_level: str = "none"
    client_name: Optional[str] = None
    error: Optional[str] = None


def hash_api_key(api_key: str) -> str:
    """Hash API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key(name: str, access_level: str = "standard", rate_limit: int = 1000) -> str:
    """Generate a new API key"""
    random_part = secrets.token_hex(16)
    api_key = f"{API_KEY_PREFIX}{random_part}"
    
    api_keys_store[api_key] = {
        "name": name,
        "access_level": access_level,
        "rate_limit": rate_limit,
        "created_at": datetime.now().isoformat(),
        "active": True
    }
    
    logger.info(f"Generated new API key for: {name}")
    return api_key


def validate_api_key(api_key: str) -> AuthResult:
    """Validate an API key"""
    if not api_key:
        return AuthResult(authenticated=False, error="No API key provided")
    
    # Check master key
    if api_key == MASTER_API_KEY:
        return AuthResult(
            authenticated=True,
            api_key=api_key,
            access_level="admin",
            client_name="Master Admin"
        )
    
    # Check registered keys
    if api_key in api_keys_store:
        key_info = api_keys_store[api_key]
        if not key_info.get("active", False):
            return AuthResult(authenticated=False, error="API key is inactive")
        
        return AuthResult(
            authenticated=True,
            api_key=api_key,
            access_level=key_info["access_level"],
            client_name=key_info["name"]
        )
    
    return AuthResult(authenticated=False, error="Invalid API key")


def revoke_api_key(api_key: str) -> bool:
    """Revoke an API key"""
    if api_key in api_keys_store:
        api_keys_store[api_key]["active"] = False
        logger.info(f"Revoked API key: {api_key[:20]}...")
        return True
    return False


def list_api_keys() -> list:
    """List all API keys (masked)"""
    return [
        {
            "key_prefix": key[:20] + "...",
            "name": info["name"],
            "access_level": info["access_level"],
            "active": info["active"],
            "created_at": info["created_at"]
        }
        for key, info in api_keys_store.items()
    ]


async def get_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
    api_key_query: str = Security(API_KEY_QUERY)
) -> Optional[str]:
    """Extract API key from header or query parameter"""
    return api_key_header or api_key_query


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Depends(get_api_key)
) -> AuthResult:
    """
    Verify API key and return authentication result.
    This is a soft verification - it returns the result but doesn't block.
    """
    # Check if authentication is disabled (for development)
    if os.getenv("DISABLE_AUTH", "false").lower() == "true":
        return AuthResult(
            authenticated=True,
            access_level="admin",
            client_name="Development Mode"
        )
    
    return validate_api_key(api_key)


async def require_api_key(
    auth_result: AuthResult = Depends(verify_api_key)
) -> AuthResult:
    """
    Require valid API key - raises exception if not authenticated.
    Use this dependency for protected endpoints.
    """
    if not auth_result.authenticated:
        raise HTTPException(
            status_code=401,
            detail=auth_result.error or "Authentication required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return auth_result


async def require_admin_key(
    auth_result: AuthResult = Depends(require_api_key)
) -> AuthResult:
    """Require admin-level API key"""
    if auth_result.access_level != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return auth_result


async def require_full_access(
    auth_result: AuthResult = Depends(require_api_key)
) -> AuthResult:
    """Require full or admin access level"""
    if auth_result.access_level not in ["admin", "full"]:
        raise HTTPException(
            status_code=403,
            detail="Full access required"
        )
    return auth_result


# Access level permissions
ACCESS_PERMISSIONS = {
    "admin": ["read", "write", "delete", "admin"],
    "full": ["read", "write"],
    "standard": ["read", "write"],
    "readonly": ["read"]
}


def has_permission(access_level: str, permission: str) -> bool:
    """Check if access level has specific permission"""
    return permission in ACCESS_PERMISSIONS.get(access_level, [])
