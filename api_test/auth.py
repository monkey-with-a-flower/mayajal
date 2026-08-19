from collections.abc import Callable
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, decode
from sqlalchemy.orm import Session

from api_test.config import AUTH_MODE, ENTRA_AUDIENCE, ENTRA_CLIENT_ID, ENTRA_TENANT_ID, require_entra_config
from api_test.database import get_db
from api_test.models import Role, User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return "pbkdf2_sha256$310000$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def unauthorized(detail: str = "Authentication is required."):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def entra_role(claims: dict) -> Role:
    names = {str(role).lower() for role in claims.get("roles", [])}
    if any(name in {"admin", "administrator", "mayajal.admin"} for name in names):
        return Role.admin
    if any(name in {"teacher", "instructor", "mayajal.teacher"} for name in names):
        return Role.teacher
    return Role.student


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        unauthorized()
    token = credentials.credentials
    if AUTH_MODE == "dev":
        if not token.startswith("dev:"):
            unauthorized("Use a development token from /auth/login.")
        username = token.removeprefix("dev:")
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            unauthorized("Development user is unknown.")
        return user

    if AUTH_MODE != "entra":
        raise HTTPException(status_code=500, detail="AUTH_MODE must be dev or entra.")
    try:
        require_entra_config()
        issuer = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0"
        jwks = PyJWKClient(f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/discovery/v2.0/keys")
        key = jwks.get_signing_key_from_jwt(token).key
        claims = decode(token, key, algorithms=["RS256"], audience=ENTRA_AUDIENCE or ENTRA_CLIENT_ID, issuer=issuer)
    except Exception as error:
        unauthorized(f"Microsoft Entra token validation failed: {error}")

    object_id = claims.get("oid")
    if not object_id:
        unauthorized("Microsoft Entra token is missing the oid claim.")
    user = db.query(User).filter(User.entra_object_id == object_id).first()
    resolved_role = entra_role(claims)
    if user is None:
        user = User(
            entra_object_id=object_id,
            email=claims.get("preferred_username", f"{object_id}@entra.local"),
            name=claims.get("name", claims.get("preferred_username", object_id)),
            role=resolved_role,
        )
        db.add(user)
    else:
        user.name = claims.get("name", user.name)
        user.email = claims.get("preferred_username", user.email)
        user.role = resolved_role
    db.commit()
    db.refresh(user)
    return user


def require_roles(*roles: Role) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot perform this action.")
        return user
    return dependency
