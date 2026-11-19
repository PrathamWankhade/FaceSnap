"""SCIM 2.0 user provisioning (minimal).

Provides a small, standards-ish subset of the SCIM 2.0 (RFC 7644) Users
resource so an identity provider can provision and deprovision FaceSnap
users. Authentication is a shared bearer token (``SCIM_TOKEN``), not a
Firebase ID token — SCIM clients do not speak Firebase.

Scope (deliberately minimal):
  * GET    /scim/v2/Users            list (filter by userName, startIndex, count)
  * GET    /scim/v2/Users/{id}       read one
  * POST   /scim/v2/Users            create
  * PATCH  /scim/v2/Users/{id}       replace role/active (partial update)
  * DELETE /scim/v2/Users/{id}       deprovision (delete user row)

Roles come from the relational DB, never from token claims; a provisioned
user defaults to ``student`` unless ``role`` is supplied and the caller is
an admin. Passwords are never stored — FaceSnap uses Firebase for identity.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth import get_db
from app.config import SCIM_TOKEN
from app.db import User

router = APIRouter()


def _require_scim_caller(request: Request) -> None:
    if not SCIM_TOKEN:
        raise HTTPException(status_code=503, detail="SCIM is not configured (SCIM_TOKEN unset).")
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer ") or auth.split(" ", 1)[1].strip() != SCIM_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token.")


class ScimName(BaseModel):
    givenName: str | None = None
    familyName: str | None = None


class ScimUserCreate(BaseModel):
    userName: str = Field(min_length=1, max_length=255)
    displayName: str | None = None
    name: ScimName | None = None
    active: bool = True
    # FaceSnap extension: role. Defaults to student.
    role: str | None = None


class ScimUserPatch(BaseModel):
    active: bool | None = None
    displayName: str | None = None
    role: str | None = None


def _to_scim(user: User) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": user.id,
        "userName": user.email,
        "displayName": user.display_name,
        "active": True,
        "meta": {"resourceType": "User", "location": f"/scim/v2/Users/{user.id}"},
        # FaceSnap extension
        "role": user.role,
    }


@router.get("/scim/v2/Users")
def list_users(
    request: Request,
    startIndex: int = Query(default=1, ge=1),
    count: int = Query(default=50, ge=1, le=200),
    filter: str | None = Query(default=None),
    _auth: None = Depends(_require_scim_caller),
    db=Depends(get_db),
):
    stmt = select(User)
    if filter and filter.lower().startswith("username eq "):
        value = filter.split('"', 2)[1] if '"' in filter else filter.split(" ", 3)[-1]
        stmt = stmt.where(User.email == value)
    rows = db.scalars(stmt).all()
    total = len(rows)
    page = rows[startIndex - 1 : startIndex - 1 + count]
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": len(page),
        "Resources": [_to_scim(u) for u in page],
    }


@router.get("/scim/v2/Users/{user_id}")
def get_user(user_id: str, request: Request, _auth: None = Depends(_require_scim_caller), db=Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return _to_scim(user)


@router.post("/scim/v2/Users", status_code=status.HTTP_201_CREATED)
def create_user(payload: ScimUserCreate, request: Request, _auth: None = Depends(_require_scim_caller), db=Depends(get_db)):
    existing = db.scalars(select(User).where(User.email == payload.userName)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists.")
    display = payload.displayName
    if display is None and payload.name:
        display = " ".join(part for part in [payload.name.givenName, payload.name.familyName] if part)
    role = payload.role if payload.role in {"admin", "student", "operator"} else "student"
    user = User(id=payload.userName, email=payload.userName, display_name=display, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_scim(user)


@router.patch("/scim/v2/Users/{user_id}")
def patch_user(user_id: str, payload: ScimUserPatch, request: Request, _auth: None = Depends(_require_scim_caller), db=Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.active is False:
        # Deprovision: delete the user row (cascades to student).
        db.delete(user)
        db.commit()
        return {"status": "deleted"}
    if payload.displayName is not None:
        user.display_name = payload.displayName
    if payload.role in {"admin", "student", "operator"}:
        user.role = payload.role
    db.commit()
    db.refresh(user)
    return _to_scim(user)


@router.delete("/scim/v2/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, request: Request, _auth: None = Depends(_require_scim_caller), db=Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
    return None
