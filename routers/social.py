from fastapi import APIRouter, HTTPException
from database import get_db_connection
import os

# 진짜 레벨업 조건표(정답지)를 가져옵니다.
try:
    from services.gamification import LEVEL_TABLE
except ImportError:
    LEVEL_TABLE = {1: 100, 2: 300, 3: 600, 4: 1000, 5: 1500}

router = APIRouter()

# 🏆 [랭킹 시스템] 총 자산(현금 + 주식) 순위 TOP 10 조회
@router.get("/ranking")
async def get_ranking():
    conn = await get_db_connection()
    try:
        # 1. 모든 유저 정보 가져오기
        async with conn.execute("SELECT id, username, level, balance, exp FROM users") as cursor:
            users = await cursor.fetchall()
            
        ranking_list = []
        
        # 2. 각 유저별로 '총 자산' 계산하기
        for user in users:
            user_id = user["id"]
            cash = user["balance"]
            
            # 이 유저의 보유 주식 가져오기
            async with conn.execute("""
                SELECT h.quantity, h.average_price, s.current_price 
                FROM holdings h
                JOIN stocks s ON h.company_name = s.company_name
                WHERE h.user_id = ?
            """, (user_id,)) as cursor:
                holdings = await cursor.fetchall()
            
            total_stock_value = 0
            total_invested = 0
            
            for h in holdings:
                current_price = h["current_price"]
                qty = h["quantity"]
                avg_price = h["average_price"]
                
                total_stock_value += (current_price * qty)
                total_invested += (avg_price * qty)
                
            # 총 자산 = 현금 + 주식 평가금
            total_assets = cash + total_stock_value
            
            # 통합 수익률 계산 (투자 원금 대비)
            profit_rate = 0.0
            if total_invested > 0:
                profit_rate = ((total_stock_value - total_invested) / total_invested) * 100
            
            ranking_list.append({
                "username": user["username"],
                "level": user["level"] if user["level"] else 1,
                "total_assets": int(total_assets),
                "profit_rate": round(profit_rate, 2),
                "exp": user["exp"]
            })
            
        # 3. 총 자산 순서대로 내림차순 정렬 (부자가 1등!)
        ranking_list.sort(key=lambda x: x["total_assets"], reverse=True)
        
        # 4. 랭킹 번호 매겨서 반환 (상위 10명만)
        result = []
        for i, item in enumerate(ranking_list[:100], 1):
            result.append({
                "rank": i,
                "username": item["username"],
                "level": item["level"],
                "total_assets": item["total_assets"],
                "profit_rate": item["profit_rate"],
                "exp": item["exp"]
            })
            
        return result
    finally:
        await conn.close()

# 레벨 및 경험치 조회 (기존 코드 그대로 유지)
@router.get("/my-profile/{user_id}")
async def get_my_profile(user_id: str):
    conn = await get_db_connection()
    try:
        # 1. 내 정보 가져오기
        async with conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        
        if not user:
            return None

        # 2. 완료한 퀘스트 개수 세기 (업적 점수용)
        async with conn.execute(
            "SELECT count(*) FROM user_quests WHERE user_id = (SELECT id FROM users WHERE username = ?) AND is_completed = 1", 
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            quest_count = row[0] if row else 0

        current_lvl = user['level']
        next_goal = LEVEL_TABLE.get(current_lvl, 999999)
        current_exp = user['exp'] if user['exp'] else 0

        return {
            "username": user['username'],
            "level": current_lvl,
            "balance": user['balance'],
            "quest_cleared": quest_count,
            "current_exp": current_exp,
            "next_level_exp": next_goal
        }
    finally:
        await conn.close()