from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db # 👈 새로운 연결 통로 가져오기
import os

router = APIRouter(prefix="/api/rank", tags=["Ranking"])

# routers/rank.py (스냅샷 읽기 모드)
@router.get("/top")
def get_top_ranking(db: Session = Depends(get_db)): # 👈 async 제거, aiosqlite 대신 Session 사용
    # text() 함수로 SQL 쿼리를 감싸서 실행합니다.
    result = db.execute(text("""
        SELECT rank, user_id, username, total_asset, profit_rate 
        FROM ranking_snapshot 
        ORDER BY rank ASC
    """))
    
    # 결과를 딕셔너리 리스트로 변환하여 반환
    return [dict(row._mapping) for row in result]
    
    # 1. 현재 주가 정보 가져오기 (딕셔너리로 변환: {'삼성전자': 78000, ...})
    cursor = await db.execute("SELECT company_name, current_price FROM stocks")
    stock_rows = await cursor.fetchall()
    current_prices = {row[0]: row[1] for row in stock_rows}

    # 2. 유저 목록 가져오기
    cursor = await db.execute("SELECT id, username, current_balance FROM users")
    users = await cursor.fetchall()
    
    ranking_list = []

    for user in users:
        user_id, username, cash = user[0], user[1], user[2]
        
        # 3. 이 유저의 보유 주식 가져오기
        cursor = await db.execute("SELECT company_name, quantity FROM holdings WHERE user_id = ?", (user_id,))
        holdings = await cursor.fetchall()
        
        stock_assets = 0
        for holding in holdings:
            name, qty = holding[0], holding[1]
            # 현재가가 있으면 곱해서 더하고, 없으면(상장폐지 등) 0원 처리
            price = current_prices.get(name, 0)
            stock_assets += price * qty
            
        total_asset = cash + stock_assets
        
        # 수익률 계산 (원금 100만원 가정)
        initial_capital = 1000000 
        profit_rate = ((total_asset - initial_capital) / initial_capital) * 100

        ranking_list.append({
            "rank": 0,
            "user_id": user_id,
            "username": username,
            "total_asset": int(total_asset),
            "profit_rate": round(profit_rate, 2)
        })

    # 4. 자산 순으로 정렬 (내림차순)
    ranking_list.sort(key=lambda x: x["total_asset"], reverse=True)

    # 5. 등수 매기기 (1등부터 순서대로)
    for index, item in enumerate(ranking_list):
        item["rank"] = index + 1

    return ranking_list