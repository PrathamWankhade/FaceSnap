"""Firebase ID-token authentication for FastAPI.

- Verifies Firebase ID tokens with firebase-admin when configured.
- Controlled by REQUIRE_AUTH (default "false" for local dev, "true" in prod).
- Camera/service endpoints can use require_service_or_user with PI_SERVICE_KEY.
"""
import os

from fastapi import Depends, Header, HTTPException, status

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
PI_SERVICE_KEY = os.getenv("PI_SERVICE_KEY", "")

_admin_init_attempted = False
_admin_ready = False


def _ensure_admin():
    global _admin_init_attempted, _admin_ready
    if _admin_init_attempted:
        return _admin_ready
    _admin_init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials, auth as admin_auth  # noqa: F401

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


def require_role(*allowed: str):
    async def checker(user=Depends(get_current_user)):
        role = user.get("role", "student")
        # Firebase custom claims may carry role; default to student.
        if allowed and role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role.")
        return user

    return checker


async def require_camera_caller(
    authorization: str | None = Header(default=None),
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
):
    """Allow either a service key (Pi/devices) or a normal authenticated user."""
    if PI_SERVICE_KEY and x_service_key and x_service_key == PI_SERVICE_KEY:
        return {"uid": "pi-service", "role": "operator"}
    return await get_current_user(authorization)
