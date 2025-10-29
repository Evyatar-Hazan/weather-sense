"""
Security and authentication for FastAPI application.
"""
import os
from typing import Optional
from fastapi import HTTPException, Security, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


security = HTTPBearer()


def get_api_key() -> str:
    """Get API key from environment variables."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is required")
    return api_key


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """Verify API key from Authorization header."""
    try:
        expected_key = get_api_key()
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if credentials.credentials != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return credentials.credentials
        
    except ValueError as e:
        # API_KEY not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured"
        )


def verify_api_key_header(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify API key from x-api-key header."""
    try:
        expected_key = get_api_key()
        
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing x-api-key header"
            )
        
        if x_api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        return x_api_key
        
    except ValueError as e:
        # API_KEY not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured"
        )