import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


def _svc() -> AuthService:
    return AuthService()


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest):
    result = await _svc().signup_patient(body.email, body.password, body.name)
    if result is None:
        raise HTTPException(status_code=409, detail="Email already registered")
    return result


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    result = await _svc().login(body.email, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return result


@router.get("/me", response_model=UserOut)
async def me(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    try:
        payload = decode_token(credentials.credentials)
        email: str | None = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await _svc().get_current_user(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
