"""The FastAPI application: the one object every request goes through.

Uvicorn (locally) and Vercel (in production) both start the server by
importing `app` from this module.
"""

from fastapi import APIRouter, FastAPI

app = FastAPI(title="SchoolFlow Result Portal API")

# Every endpoint lives under /api/v1 (decision D-015), so a future /api/v2
# can sit beside it without breaking the frontend.
api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health")
def health() -> dict[str, str]:
    """Liveness check (D-126): no database, safe to call often, reveals nothing."""
    return {"status": "ok"}


app.include_router(api_v1)
