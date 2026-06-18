from fastapi import APIRouter, HTTPException
from db.connection import get_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {exc}")
    return {"status": "ok"}