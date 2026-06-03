import os
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

LOGTO_ENDPOINT = os.getenv("LOGTO_ENDPOINT", "https://<your-logto-tenant>.logto.app/")
LOGTO_API_RESOURCE = os.getenv("LOGTO_API_RESOURCE", "https://spiir.seame.click/api")
JWKS_URL = f"{LOGTO_ENDPOINT.rstrip('/')}/oidc/jwks"

jwks_client = jwt.PyJWKClient(JWKS_URL)

def verify_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES384", "RS256"],
            audience=LOGTO_API_RESOURCE,
        )
        return payload
    except jwt.exceptions.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
