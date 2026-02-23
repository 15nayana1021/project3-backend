from fastapi import APIRouter, HTTPException, Depends, Header, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from database import get_db
import os

try:
    from services.gamification import gain_exp, check_quest
except ImportError:
    def gain_exp(*args, **kwargs): pass
    def check_quest(*args, **kwargs): pass

router = APIRouter(prefix="/api/trade", tags=["Trade"])

# 1. 데이터 모델 (Schema)
class UserCreate(BaseModel):
    username: str

class TradeRequest(BaseModel):
    user_id: int
    company_name: str
    price: float
    quantity: int

# 2. 지갑 생성 및 초기 자금 지급 API (가입)
@router.post("/user/init")
def init_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # 유저 중복 확인
        user_check = db.execute(text("SELECT id, balance FROM users WHERE username = :username"), {"username": user.username}).fetchone()
        
        if user_check:
            return {
                "status": "exists", 
                "user_id": user_check[0], 
                "balance": user_check[1], 
                "message": f"이미 계정이 있습니다. 환영합니다, {user.username}님!"
            }

        # 1. 유저 생성 (RETURNING id 사용)
        new_user = db.execute(
            text("INSERT INTO users (username, balance) VALUES (:username, 1000000) RETURNING id"), 
            {"username": user.username}
        ).fetchone()
        
        user_id = new_user[0]
        balance = 1000000.0
        
        # 2. 원장(Ledger)에 기록
        db.execute(text("""
            INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
            VALUES (:user_id, 'DEPOSIT', 1000000, 1000000, '신규 가입 축하금')
        """), {"user_id": user_id})
        
        db.commit()
        
        return {
            "status": "created", 
            "user_id": user_id,
            "balance": balance, 
            "message": f"환영합니다, {user.username}님! 지갑 생성 완료! (100만원 지급)"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# 4. 내 정보(잔액) 조회 API
@router.get("/user/{user_id}")
def get_user_info(user_id: int, db: Session = Depends(get_db)):
    # 1. 잔액 조회
    user_row = db.execute(text("SELECT username, balance FROM users WHERE id = :user_id"), {"user_id": user_id}).fetchone()
    
    if not user_row:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        
    # 2. 보유 주식 조회
    holdings_rows = db.execute(text("""
        SELECT company_name, quantity, average_price 
        FROM holdings 
        WHERE user_id = :user_id AND quantity > 0
    """), {"user_id": user_id}).fetchall()
    
    return {
        "username": user_row[0],
        "balance": user_row[1],
        "holdings": [dict(row._mapping) for row in holdings_rows]
    }

# 5. 보상 지급 API (퀘스트, 배당금 등)
class RewardRequest(BaseModel):
    user_id: int
    amount: float
    description: str

@router.post("/reward")
def give_reward(reward: RewardRequest, db: Session = Depends(get_db)):
    try:
        # 유저 확인
        row = db.execute(text("SELECT balance FROM users WHERE id = :user_id"), {"user_id": reward.user_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
            
        balance = row[0]
        new_balance = balance + reward.amount
        
        # 잔액 업데이트 및 기록
        db.execute(text("UPDATE users SET balance = :new_balance WHERE id = :user_id"), 
                   {"new_balance": new_balance, "user_id": reward.user_id})
        
        db.execute(text("""
            INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
            VALUES (:user_id, 'REWARD', :amount, :new_balance, :desc)
        """), {"user_id": reward.user_id, "amount": reward.amount, "new_balance": new_balance, "desc": reward.description})

        db.commit()

        return {
            "status": "success", "message": f"보상 지급 완료: {reward.amount}원",
            "balance": new_balance, "reason": reward.description
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"보상 지급 실패: {str(e)}")

# 7. 지정가 주문 시스템
class OrderRequest(BaseModel):
    user_id: int
    ticker: str = None
    company_name: str = None
    order_type: str
    side: str = None
    price: int
    quantity: int
    game_date: str = None

@router.post("/order")
def place_order(req: OrderRequest, db: Session = Depends(get_db)):
    try:
        # 1. 유저 확인 및 ID 정수 변환 (PostgreSQL은 타입을 엄격히 따집니다)
        user_id = int(req.user_id)
        target_ticker = req.ticker
        side = req.side.upper()
        quantity = int(req.quantity)
        
        # 2. 현재가 조회 (companies 테이블의 ticker 컬럼 사용)
        # 💡 테이블 이름이 'stocks'인지 'companies'인지 database.py를 확인하세요! 
        # 여기서는 'companies'라고 가정합니다.
        comp_row = db.execute(
            text("SELECT current_price FROM companies WHERE ticker = :ticker"), 
            {"ticker": target_ticker}
        ).fetchone()
        
        if not comp_row:
            return {"success": False, "message": "존재하지 않는 종목입니다.", "msg": "존재하지 않는 종목입니다."}
            
        current_price = comp_row[0]
        total_amount = current_price * quantity

        # 3. 매수 시 잔액 확인
        if side == "BUY":
            user_row = db.execute(
                text("SELECT balance FROM users WHERE id = :uid"), 
                {"uid": user_id}
            ).fetchone()
            
            if not user_row or user_row[0] < total_amount:
                return {"success": False, "message": "잔액이 부족합니다.", "msg": "잔액이 부족합니다."}

        # 4. 주문 기록 (PostgreSQL 컬럼명 주의: symbol -> ticker)
        # 💡 만약 DB 설계 시 'symbol'을 썼다면 아래 ticker를 symbol로 바꾸세요.
        order_res = db.execute(text("""
            INSERT INTO orders (user_id, ticker, side, quantity, price, status, created_at)
            VALUES (:uid, :tk, :sd, :qty, :pr, 'PENDING', :ts)
            RETURNING id
        """), {
            "uid": user_id, "tk": target_ticker, "sd": side, 
            "qty": quantity, "pr": current_price, "ts": datetime.now()
        }).fetchone()
        
        db.commit()
        
        return {
            "success": True, 
            "message": "주문이 성공적으로 접수되었습니다!", 
            "order_id": order_res[0]
        }

    except Exception as e:
        db.rollback()
        print(f"🚨 주문 처리 중 치명적 에러: {e}") # 로그 스트림에 출력됨
        return {"success": False, "message": f"서버 오류: {str(e)}", "msg": str(e)}

@router.get("/orders/{user_id}")
def get_my_orders(user_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, company_name, order_type, price, quantity, created_at, status
        FROM orders WHERE user_id = :uid ORDER BY created_at DESC LIMIT 20
    """), {"uid": user_id}).fetchall()
    return [dict(row._mapping) for row in rows]

@router.delete("/order/{order_id}")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    try:
        order = db.execute(text("SELECT * FROM orders WHERE id = :oid"), {"oid": order_id}).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
            
        order_dict = dict(order._mapping)
        current_status = order_dict['status'].strip()
        
        if current_status != 'PENDING':
            raise HTTPException(status_code=400, detail=f"취소 불가: 현재 상태가 '{current_status}' 입니다.")
            
        user_id = order_dict['user_id']
        price = order_dict['price']
        quantity = order_dict['quantity']
        
        if order_dict['order_type'] == 'BUY':
            refund = price * quantity
            db.execute(text("UPDATE users SET balance = balance + :refund WHERE id = :uid"), {"refund": refund, "uid": user_id})
        elif order_dict['order_type'] == 'SELL':
            db.execute(text("UPDATE holdings SET quantity = quantity + :qty WHERE user_id = :uid AND company_name = :ticker"), 
                       {"qty": quantity, "uid": user_id, "ticker": order_dict['company_name']})
            
        db.execute(text("UPDATE orders SET status = 'CANCELLED' WHERE id = :oid"), {"oid": order_id})
        db.commit()
        
        return {"status": "success", "message": "주문이 취소되었습니다."}
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 에러: {str(e)}")

# 프로세스 오더 생략 (자동 체결 엔진에 맡김)

def verify_level_5(db: Session = Depends(get_db)):
    user_id = 1
    row = db.execute(text("SELECT level FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
    current_level = row[0] if row else 1
    
    if current_level < 5:
        raise HTTPException(status_code=403, detail=f"호가창은 LV.5부터 이용 가능합니다. (현재: LV.{current_level})")
    return True

@router.get("/orderbook/{company_name}")
def get_order_book(company_name: str, is_authorized: bool = Depends(verify_level_5)):
    return {
        "company": company_name,
        "asks": [{"price": 81000, "qty": 10}, {"price": 82000, "qty": 50}],
        "bids": [{"price": 79000, "qty": 20}, {"price": 78000, "qty": 100}]
    }

@router.get("/orders/all/{user_id}")
def get_all_orders_all(user_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, company_name, order_type as side, price, quantity, status, game_date, created_at
        FROM orders WHERE user_id = :uid ORDER BY created_at DESC LIMIT 50
    """), {"uid": user_id}).fetchall()
    return [dict(row._mapping) for row in rows]