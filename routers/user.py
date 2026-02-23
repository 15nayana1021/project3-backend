from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db # 👈 새로운 연결 통로 가져오기
import os

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/status")
def get_user_status( # 👈 async 제거
    x_user_id: int = Header(1, alias="X-User-ID"),
    db: Session = Depends(get_db) # 👈 aiosqlite.Connection 대신 Session 사용
):
    target_user_id = x_user_id
    
    # 예시: 만약 유저 정보를 가져오는 쿼리가 아래에 있었다면 이렇게 씁니다.
    # query = text("SELECT * FROM users WHERE id = :user_id")
    # user = db.execute(query, {"user_id": target_user_id}).fetchone()
    # return dict(user._mapping) if user else None
    
    return {"user_id": target_user_id, "status": "ok"} # 기존 로직에 맞게 유지/수정하세요!

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