from fastapi import APIRouter, Depends, HTTPException, Header
import aiosqlite
from database import get_db_connection
import os

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/status")
async def get_user_status(
    x_user_id: int = Header(1, alias="X-User-ID"),
    db: aiosqlite.Connection = Depends(get_db_connection)
):
    target_user_id = x_user_id

    cursor = await db.execute("SELECT username, level, exp, balance FROM users WHERE id = ?", (target_user_id,))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    
    return {
        "user_id": target_user_id,
        "username": row[0],
        "level": row[1],
        "exp": row[2],
        "balance": row[3]
    }