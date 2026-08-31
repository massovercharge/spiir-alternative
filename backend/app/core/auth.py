"""Pluggable authentication middleware for the Peng API.

Controlled by the AUTH_PROVIDER environment variable:
    - "none"  : No authentication (default — for local / VPN use)
    - "basic" : Simple username/password via HTTP Basic Auth
    - "logto" : Generic OpenID Connect via Logto

Household Context:
The `get_auth_dependency` now not only verifies the JWT but also ensures
the user exists in the database, has a default Household, and sets the
`current_household_id` contextvar based on the `X-Household-Id` header.
"""

from __future__ import annotations

import os
import secrets
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlmodel import Session, select

import app.models as models
from app.models import Household, HouseholdMember, User, current_household_id

AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "none").strip().lower()

# ---------------------------------------------------------------------------
# Core User/Household Sync
# ---------------------------------------------------------------------------


def _sync_user_and_household(
    request: Request, logto_id: str, email: str = "", name: str = ""
) -> dict[str, Any]:
    """Ensure user exists, validate household access, and set contextvar."""
    from sqlmodel import func

    email = email.lower().strip() if email else ""
    try:
        with Session(models.engine) as session:
            # 1. Sync User
            user = session.exec(select(User).where(User.logto_id == logto_id)).first()
            if not user and email:
                user = session.exec(select(User).where(func.lower(User.email) == email)).first()
                if user:
                    user.logto_id = logto_id
                    if name and not user.name:
                        user.name = name
                    session.add(user)
                    session.commit()
                    session.refresh(user)

            if not user:
                user = User(logto_id=logto_id, email=email, name=name)
                session.add(user)
                session.commit()
                session.refresh(user)

                # Create default household
                hh = Household(name="Min Økonomi")
                session.add(hh)
                session.commit()
                session.refresh(hh)

                # Link user as owner
                member = HouseholdMember(household_id=hh.id, user_id=user.id, role="owner")
                session.add(member)
                session.commit()
            else:
                # Update email/name on existing user record if provided and missing/changed
                updated = False

                # Always check for pending invites for this email, even if the email hasn't changed.
                # This fixes issues where pending invites were created with different casing.
                if email:
                    pending_users = session.exec(
                        select(User).where(
                            func.lower(User.email) == email, User.logto_id.startswith("pending:")
                        )
                    ).all()

                    for pending_user in pending_users:
                        # Transfer memberships from pending to real user
                        memberships = session.exec(
                            select(HouseholdMember).where(
                                HouseholdMember.user_id == pending_user.id
                            )
                        ).all()
                        for m in memberships:
                            # Avoid duplicate memberships
                            existing = session.exec(
                                select(HouseholdMember).where(
                                    HouseholdMember.user_id == user.id,
                                    HouseholdMember.household_id == m.household_id,
                                )
                            ).first()
                            if not existing:
                                m.user_id = user.id
                                session.add(m)
                            else:
                                session.delete(m)

                        # Remove the pending stub
                        session.delete(pending_user)
                        updated = True

                if email and (not user.email or user.email.lower() != email):
                    user.email = email
                    updated = True

                if name and user.name != name:
                    user.name = name
                    updated = True

                if updated:
                    session.add(user)
                    session.commit()
                    session.refresh(user)

            # 2. Determine Household
            requested_hh_id = request.headers.get("X-Household-Id")
            active_hh_id = None

            if requested_hh_id:
                # Validate membership
                membership = session.exec(
                    select(HouseholdMember).where(
                        HouseholdMember.user_id == user.id,
                        HouseholdMember.household_id == requested_hh_id,
                    )
                ).first()
                if not membership:
                    raise HTTPException(status_code=403, detail="Access to household denied")
                active_hh_id = requested_hh_id
            else:
                # Fallback to first available household
                membership = session.exec(
                    select(HouseholdMember).where(HouseholdMember.user_id == user.id)
                ).first()
                if not membership:
                    # Edge case: user exists but lost all households
                    hh = Household(name="Min Økonomi")
                    session.add(hh)
                    session.commit()
                    session.refresh(hh)
                    member = HouseholdMember(household_id=hh.id, user_id=user.id, role="owner")
                    session.add(member)
                    session.commit()
                    active_hh_id = hh.id
                else:
                    active_hh_id = membership.household_id

            # 3. Set Context
            current_household_id.set(active_hh_id)

            return {
                "sub": user.logto_id,
                "user_id": user.id,
                "household_id": active_hh_id,
            }
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise e


# ---------------------------------------------------------------------------
# Provider: none (no authentication)
# ---------------------------------------------------------------------------


async def _verify_none(request: Request) -> dict[str, Any]:
    """No-op authenticator — allows all requests."""
    return _sync_user_and_household(request, "local_user", "local@example.com", "Lokal Bruger")


# ---------------------------------------------------------------------------
# Provider: basic (HTTP Basic Auth)
# ---------------------------------------------------------------------------

_basic_scheme = HTTPBasic(auto_error=False)

BASIC_USERNAME = os.getenv("PENG_AUTH_USERNAME", "admin")
BASIC_PASSWORD = os.getenv("PENG_AUTH_PASSWORD", "")


async def _verify_basic(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(_basic_scheme),
) -> dict[str, Any]:
    if not BASIC_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_PROVIDER=basic requires PENG_AUTH_PASSWORD to be set",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username, BASIC_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, BASIC_PASSWORD)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return _sync_user_and_household(request, credentials.username, credentials.username)


# ---------------------------------------------------------------------------
# Provider: logto (OIDC via Logto)
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

LOGTO_ENDPOINT = os.getenv("LOGTO_ENDPOINT", "").rstrip("/")
LOGTO_API_RESOURCE = os.getenv("LOGTO_API_RESOURCE", "")
JWKS_URL = os.getenv("LOGTO_JWKS_URL", f"{LOGTO_ENDPOINT}/oidc/jwks" if LOGTO_ENDPOINT else "")

jwks_client = (
    PyJWKClient(JWKS_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; Peng/1.0)"})
    if JWKS_URL
    else None
)


async def _verify_logto(
    request: Request, token: HTTPBasicCredentials | None = Depends(_bearer_scheme)
) -> dict[str, Any]:
    """Validate JWT token issued by Logto."""
    if not LOGTO_ENDPOINT or not LOGTO_API_RESOURCE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_PROVIDER=logto requires LOGTO_ENDPOINT and LOGTO_API_RESOURCE to be set",
        )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token.credentials)
        payload = jwt.decode(
            token.credentials,
            signing_key.key,
            algorithms=["RS256", "ES384"],
            audience=LOGTO_API_RESOURCE,
            issuer=f"{LOGTO_ENDPOINT}/oidc",
        )
        email = (
            payload.get("email")
            or payload.get("primary_email")
            or payload.get("username")
            or payload.get("preferred_username")
            or ""
        )
        name = (
            payload.get("name")
            or payload.get("username")
            or payload.get("preferred_username")
            or ""
        )

        if (not email or not name) and LOGTO_ENDPOINT and token.credentials:
            try:
                import httpx

                resp = httpx.get(
                    f"{LOGTO_ENDPOINT}/oidc/me",
                    headers={"Authorization": f"Bearer {token.credentials}"},
                    timeout=3.0,
                )
                if resp.status_code == 200:
                    info = resp.json()
                    email = email or info.get("email") or info.get("primary_email") or ""
                    name = (
                        name
                        or info.get("name")
                        or info.get("username")
                        or info.get("preferred_username")
                        or ""
                    )
            except Exception:
                pass

        return _sync_user_and_household(request, payload.get("sub"), email, name)
    except jwt.PyJWKClientError as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not fetch JWKS") from e
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Token expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Public dependency — use this in FastAPI route/app dependencies
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "none": _verify_none,
    "basic": _verify_basic,
    "logto": _verify_logto,
}


def get_auth_dependency():
    """Return the appropriate auth dependency based on AUTH_PROVIDER."""
    provider = _PROVIDERS.get(AUTH_PROVIDER)
    if provider is None:
        raise ValueError(
            f"Unknown AUTH_PROVIDER={AUTH_PROVIDER!r}. "
            f"Valid options: {', '.join(_PROVIDERS.keys())}"
        )
    return provider
