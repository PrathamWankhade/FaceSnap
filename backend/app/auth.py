"""Authentication + authorization for FastAPI.

- Verifies provider ID tokens with firebase-admin when configured.
- Controlled by REQUIRE_AUTH; production defaults to enforcing tokens and
  refuses to run with the development bypass.
- Resolves the authoritative role from the relational ``users`` table, not from
  token claims (provider claims rarely carry a role and must not be trusted).
- Camera/service endpoints accept either a valid service key or a staff user.
"""
import hmac
import os

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import ADMIN_EMAILS, IS_PRODUCTION, PI_SERVICE_KEY, REQUIRE_AUTH
from app.db import User, get_db

STAFF_ROLES = ("admin", "operator")

_admin_init_attempted = False
_admin_ready = False


def _ensure_admin():
    global _admin_init_attempted, _admin_ready
    if _admin_init_attempted:
        return _admin_ready
    _admin_init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials  # noqa: F401

        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        _admin_ready = True
    except Exception as e:
        print(f"Firebase Admin not configured ({e}); token verification disabled.")
        _admin_ready = False
    return _admin_ready


async def get_current_user(authorization: str | None = Header(default=None)):
    """Return decoded token claims, or a dev placeholder when auth is not required."""
    if not REQUIRE_AUTH:
        # Fail closed if someone deploys production with the bypass still on.
        if IS_PRODUCTION:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is required in production.",
            )
        return {"uid": "dev", "role": "admin", "dev_bypass": True}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty bearer token.")
    if not _ensure_admin():
        raise HTTPException(status_code=503, detail="Auth service not configured.")
    try:
        from firebase_admin import auth as admin_auth

        decoded = admin_auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID token.")


def _claims_identity(claims: dict) -> tuple[str, str | None, str | None]:
    uid = claims.get("uid") or claims.get("user_id") or claims.get("sub")
    email = claims.get("email")
    name = claims.get("name")
    return uid, email, name


def resolve_user_row(db, claims: dict) -> User:
    """Upsert the caller into ``users`` and return the authoritative record.

    The row is the single source of truth for role. New users default to
    ``student`` unless their verified email is listed in ADMIN_EMAILS (or the
    request is the explicit local-dev bypass).
    """
    uid, email, name = _claims_identity(claims)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no subject.")

    user = db.get(User, uid)
    if user is None:
        if claims.get("dev_bypass"):
            role = "admin"
        elif email and email.lower() in ADMIN_EMAILS:
            role = "admin"
        else:
            role = "student"
        user = User(id=uid, email=email, display_name=name, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    changed = False
    if email and user.email != email:
        user.email = email
        changed = True
    if name and user.display_name != name:
        user.display_name = name
        changed = True
    # Allow a configured admin email to be promoted on login.
    if email and email.lower() in ADMIN_EMAILS and user.role != "admin":
        user.role = "admin"
        changed = True
    if changed:
        db.commit()
        db.refresh(user)
    return user


async def get_current_user_row(db=Depends(get_db), claims=Depends(get_current_user)) -> User:
    return resolve_user_row(db, claims)


def require_roles(*allowed: str):
    async def checker(user: User = Depends(get_current_user_row)) -> User:
        if allowed and user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role.")
        return user

    return checker


async def require_camera_caller(
    authorization: str | None = Header(default=None),
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
    db: Session = Depends(get_db),
):
    """Allow a valid service key (Pi/devices) or a staff user.

    Regular students must never be able to read the camera stream or ask the
    matcher to identify people, so camera endpoints are staff-only.
    """
    if PI_SERVICE_KEY and x_service_key and hmac.compare_digest(x_service_key, PI_SERVICE_KEY):
        return {"uid": "pi-service", "role": "operator"}

    claims = await get_current_user(authorization)
    user = resolve_user_row(db, claims)
    if user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Camera endpoints are staff-only.")
    return user
