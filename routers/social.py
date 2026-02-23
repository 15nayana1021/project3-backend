from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import os

# 진짜 레벨업 조건표(정답지)를 가져옵니다.
try:
    from services.gamification import LEVEL_TABLE
except ImportError:
    LEVEL_TABLE = {1: 100, 2: 300, 3: 600, 4: 1000, 5: 1500}

router = APIRouter()

# 🏆 [랭킹 시스템] 총 자산(현금 + 주식) 순위 TOP 100 조회
@router.get("/ranking")
def get_ranking(db: Session = Depends(get_db)): # 👈 async 제거, Session 주입
    try:
        # 1. 모든 유저 정보 가져오기
        users = db.execute(text("SELECT id, username, level, balance, exp FROM users")).fetchall()
        
        ranking_list = []
        
        # 2. 각 유저별로 '총 자산' 계산하기
        for user in users:
            user_id = user[0]
            username = user[1]
            level = user[2] if user[2] else 1
            cash = user[3]
            exp = user[4]
            
            # 이 유저의 보유 주식 가져오기
            holdings = db.execute(text("""
                SELECT h.quantity, h.average_price, s.current_price 
                FROM holdings h
                JOIN stocks s ON h.company_name = s.company_name
                WHERE h.user_id = :user_id
            """), {"user_id": user_id}).fetchall()
            
            total_stock_value = 0
            total_invested = 0
            
            for h in holdings:
                qty = h[0]
                avg_price = h[1]
                current_price = h[2]
                
                total_stock_value += (current_price * qty)
                total_invested += (avg_price * qty)
                
            # 총 자산 = 현금 + 주식 평가금
            total_assets = cash + total_stock_value
            
            # 통합 수익률 계산 (투자 원금 대비)
            profit_rate = 0.0
            if total_invested > 0:
                profit_rate = ((total_stock_value - total_invested) / total_invested) * 100
            
            ranking_list.append({
                "username": username,
                "level": level,
                "total_assets": int(total_assets),
                "profit_rate": round(profit_rate, 2),
                "exp": exp
            })
            
        # 3. 총 자산 순서대로 내림차순 정렬 (부자가 1등!)
        ranking_list.sort(key=lambda x: x["total_assets"], reverse=True)
        
        # 4. 랭킹 번호 매겨서 반환 (상위 100명만)
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
    except Exception as e:
        print(f"❌ 랭킹 조회 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 레벨 및 경험치 조회
@router.get("/my-profile/{username}")
def get_my_profile(username: str, db: Session = Depends(get_db)): # 👈 async 제거, 매개변수 이름 명확히
    try:
        # 1. 내 정보 가져오기
        user = db.execute(text("SELECT id, username, level, balance, exp FROM users WHERE username = :uname"), {"uname": username}).fetchone()
        
        if not user:
            return None

        user_id = user[0]
        current_lvl = user[2]
        balance = user[3]
        current_exp = user[4] if user[4] else 0

        # 2. 완료한 퀘스트 개수 세기
        row = db.execute(text("""
            SELECT count(*) FROM user_quests 
            WHERE user_id = :uid AND is_completed = 1
        """), {"uid": user_id}).fetchone()
        
        quest_count = row[0] if row else 0
        next_goal = LEVEL_TABLE.get(current_lvl, 999999)

        return {
            "username": user[1],
            "level": current_lvl,
            "balance": balance,
            "quest_cleared": quest_count,
            "current_exp": current_exp,
            "next_level_exp": next_goal
        }
    except Exception as e:
        print(f"❌ 프로필 조회 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))