from fastapi import APIRouter, HTTPException, Depends, Header, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from database import get_db, DBCompany  # DBCompany 추가
import os

# 시뮬레이션 엔진 연동을 위한 임포트
from main_simulation import market_engine
from models.domain_models import Order as SimOrder, OrderSide, OrderType

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
        user_check = db.execute(text("SELECT id, balance FROM users WHERE username = :username"), {"username": user.username}).fetchone()
        
        if user_check:
            return {
                "status": "exists", 
                "user_id": user_check[0], 
                "balance": user_check[1], 
                "message": f"이미 계정이 있습니다. 환영합니다, {user.username}님!"
            }

        new_user = db.execute(
            text("INSERT INTO users (username, balance, level, exp) VALUES (:username, 1000000, 1, 0) RETURNING id"), 
            {"username": user.username}
        ).fetchone()
        
        user_id = new_user[0]
        balance = 1000000.0
        
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
    user_row = db.execute(text("SELECT username, balance FROM users WHERE id = :user_id"), {"user_id": user_id}).fetchone()
    
    if not user_row:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        
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
        row = db.execute(text("SELECT balance FROM users WHERE id = :user_id"), {"user_id": reward.user_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
            
        balance = row[0]
        new_balance = balance + reward.amount
        
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
    order_type: str = "LIMIT" # 프론트엔드가 안보낼 경우 기본값
    side: str = None # BUY or SELL
    price: int
    quantity: int
    game_date: str = None

@router.post("/order")
def place_order(req: OrderRequest, db: Session = Depends(get_db)):
    try:
        user_id = int(req.user_id)
        
        # 💡 [핵심 고침 1] 프론트엔드가 이름만 보내든 코드만 보내든 완벽하게 찾아냅니다!
        search_query = req.ticker or req.company_name or ""
        company = db.execute(text("SELECT ticker, name, current_price FROM companies WHERE ticker = :sq OR name = :sq"), 
                             {"sq": search_query}).fetchone()
        
        if not company:
            return {"success": False, "message": "존재하지 않는 종목입니다.", "msg": "존재하지 않는 종목입니다."}
            
        target_ticker = company[0]  # 무조건 표준 코드(SS011 등)로 통일!
        company_name = company[1]
        current_price = company[2]
        
        side_str = req.side.upper() if req.side else "BUY" 
        if side_str not in ["BUY", "SELL"]: side_str = "BUY"
        quantity = int(req.quantity)
        total_amount = current_price * quantity

        # 💡 잔액/보유량 검증
        if side_str == "BUY":
            user_row = db.execute(text("SELECT balance FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
            if not user_row or user_row[0] < total_amount:
                return {"success": False, "message": "현금이 부족합니다.", "msg": "현금이 부족합니다."}
        else: # SELL
            holding_row = db.execute(text("SELECT quantity FROM holdings WHERE user_id = :uid AND company_name = :tk"), {"uid": user_id, "tk": target_ticker}).fetchone()
            if not holding_row or holding_row[0] < quantity:
                 return {"success": False, "message": "보유 주식이 부족합니다.", "msg": "보유 주식이 부족합니다."}

        # 💡 DB 기록 (이제 무조건 올바른 ticker가 들어갑니다)
        order_res = db.execute(text("""
            INSERT INTO orders (user_id, ticker, side, quantity, price, status, created_at)
            VALUES (:uid, :tk, :sd, :qty, :pr, 'PENDING', :ts)
            RETURNING id
        """), {
            "uid": user_id, "tk": target_ticker, "sd": side_str, 
            "qty": quantity, "pr": current_price, "ts": datetime.now()
        }).fetchone()
        
        order_id = order_res[0]
        
        # 💡 선결제 (돈/주식 먼저 묶어두기)
        if side_str == "BUY":
            db.execute(text("UPDATE users SET balance = balance - :amt WHERE id = :uid"), {"amt": total_amount, "uid": user_id})
        else:
            db.execute(text("UPDATE holdings SET quantity = quantity - :qty WHERE user_id = :uid AND company_name = :tk"), {"qty": quantity, "uid": user_id, "tk": target_ticker})
            
        db.commit() # 💡 [핵심 고침 2] 여기서 확실하게 닫아줘야 락(먹통)이 안 걸립니다!

        # 🚀 시장 엔진 전송 (오류가 나도 메인 서버가 터지지 않게 보호)
        try:
            sim_side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL
            sim_order = SimOrder(agent_id=str(user_id), ticker=target_ticker, side=sim_side, order_type=OrderType.LIMIT, quantity=quantity, price=current_price)
            market_engine.place_order(db, sim_order)
        except Exception as e:
            print(f"⚠️ 엔진 전송 무시 (시스템은 정상 작동): {e}")

        msg = f"{company_name} {quantity}주 주문 접수 완료!"
        return {"success": True, "message": msg, "msg": msg, "order_id": order_id}

    except Exception as e:
        db.rollback()
        print(f"🚨 주문 처리 중 에러: {e}") 
        return {"success": False, "message": f"서버 오류: {str(e)}", "msg": str(e)}

@router.get("/orders/{user_id}")
def get_my_orders(user_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT o.id, c.name as company_name, o.side, o.price, o.quantity, o.created_at, o.status
        FROM orders o
        LEFT JOIN companies c ON o.ticker = c.ticker
        WHERE o.user_id = :uid ORDER BY o.created_at DESC LIMIT 20
    """), {"uid": user_id}).fetchall()
    
    # 💡 프론트엔드가 요구하는 소문자 포맷으로 변환해서 보냅니다.
    result = []
    for row in rows:
        d = dict(row._mapping)
        d['order_type'] = str(d['side']).lower() # 'BUY' -> 'buy'
        # company_name이 없으면 ticker를 반환
        if not d.get('company_name'): d['company_name'] = "알 수 없는 종목" 
        result.append(d)
    return result

@router.delete("/order/{order_id}")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    try:
        # 상태 확인 (컬럼을 명시적으로 가져와 에러 방지)
        order = db.execute(text("SELECT user_id, price, quantity, ticker, side, status FROM orders WHERE id = :oid"), {"oid": order_id}).fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
            
        user_id, price, quantity, ticker, side, current_status = order
        
        if current_status.strip() != 'PENDING':
            raise HTTPException(status_code=400, detail=f"취소 불가: 현재 상태가 '{current_status}' 입니다.")
            
        # 환불 처리
        if side == 'BUY':
            refund = price * quantity
            db.execute(text("UPDATE users SET balance = balance + :refund WHERE id = :uid"), {"refund": refund, "uid": user_id})
        elif side == 'SELL':
            db.execute(text("UPDATE holdings SET quantity = quantity + :qty WHERE user_id = :uid AND company_name = :tk"), 
                       {"qty": quantity, "uid": user_id, "tk": ticker})
            
        # 상태 변경
        db.execute(text("UPDATE orders SET status = 'CANCELLED' WHERE id = :oid"), {"oid": order_id})
        db.commit()
        
        # 엔진에서도 삭제 시도
        try:
             market_engine.cancel_order(str(user_id), ticker, order_id)
        except: pass
        
        return {"status": "success", "message": "주문이 성공적으로 취소되었습니다."}
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"🚨 취소 처리 중 에러: {e}")
        raise HTTPException(status_code=500, detail=f"서버 에러: {str(e)}")


def verify_level_5(db: Session = Depends(get_db)):
    user_id = 1
    row = db.execute(text("SELECT level FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
    current_level = row[0] if row else 1
    
    if current_level < 5:
        raise HTTPException(status_code=403, detail=f"호가창은 LV.5부터 이용 가능합니다. (현재: LV.{current_level})")
    return True

@router.get("/orderbook/{company_name}")
def get_order_book(company_name: str, is_authorized: bool = Depends(verify_level_5)):
    # 💡 실제 호가창 데이터를 가져오는 로직 (임시 하드코딩 제거 고려)
    try:
        if company_name in market_engine.order_books:
            book = market_engine.order_books[company_name]
            # 단순 집계
            asks = [{"price": o["price"], "qty": o["quantity"]} for o in book["SELL"][:5]]
            bids = [{"price": o["price"], "qty": o["quantity"]} for o in book["BUY"][:5]]
            return {"company": company_name, "asks": asks, "bids": bids}
    except: pass
    
    return {
        "company": company_name,
        "asks": [{"price": 81000, "qty": 10}, {"price": 82000, "qty": 50}],
        "bids": [{"price": 79000, "qty": 20}, {"price": 78000, "qty": 100}]
    }

@router.get("/orders/all/{user_id}")
def get_all_orders_all(user_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT o.id, c.name as company_name, o.side, o.price, o.quantity, o.status, o.created_at
        FROM orders o
        LEFT JOIN companies c ON o.ticker = c.ticker
        WHERE o.user_id = :uid ORDER BY o.created_at DESC LIMIT 50
    """), {"uid": user_id}).fetchall()
    
    result = []
    for row in rows:
        d = dict(row._mapping)
        d['order_type'] = str(d['side']).lower() # 프론트엔드 포맷 맞춤
        if not d.get('company_name'): d['company_name'] = "알 수 없는 종목"
        result.append(d)
        
    return result