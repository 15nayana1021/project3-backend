from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import aiosqlite
from database import get_db_connection
from services.gamification import gain_exp, check_quest
from models.domain_models import Order, OrderType, OrderSide
from database import DB_PATH
import os

router = APIRouter(prefix="/api/trade", tags=["Trade"])

DB_PATH = "/home/site/wwwroot/stock_game.db" if os.getenv("WEBSITE_HOSTNAME") else "stock_game.db"

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
async def init_user(user: UserCreate, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [안전 호환 모드] 유저 생성 및 초기 자금 지급
    """
    try:
        # 1. 유저 생성 (INSERT 실행)
        cursor = await db.execute(
            "INSERT INTO users (username, balance) VALUES (?, 1000000)", 
            (user.username,)
        )
        await db.commit()
        
        # 2. 방금 만든 유저의 ID 확인 (RETURNING 대신 lastrowid 사용)
        user_id = cursor.lastrowid
        balance = 1000000.0
        
        # 3. 원장(Ledger)에 가입 축하금 기록
        await db.execute("""
            INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
            VALUES (?, 'DEPOSIT', 1000000, 1000000, '신규 가입 축하금')
        """, (user_id,))
        
        await db.commit()
        
        return {
            "status": "created", 
            "user_id": user_id,
            "balance": balance, 
            "message": f"환영합니다, {user.username}님! 지갑 생성 완료! (100만원 지급)"
        }
        
    except aiosqlite.IntegrityError:
        # 이미 존재하는 아이디인 경우
        cursor = await db.execute("SELECT id, balance FROM users WHERE username = ?", (user.username,))
        row = await cursor.fetchone()
        return {
            "status": "exists", 
            "user_id": row[0], 
            "balance": row[1], 
            "message": f"이미 계정이 있습니다. 환영합니다, {user.username}님!"
        }


# 3. 주식 매수 API (Transaction)
# @router.post("/buy")
# async def buy_stock(trade: TradeRequest, db: aiosqlite.Connection = Depends(get_db_connection)):
#     """
#     [매수 트랜잭션]
#     1. 잔액 확인 (balance) -> 2. 잔액 차감 -> 3. 주식 지급 -> 4. 경험치/퀘스트
#     """
#     total_cost = trade.price * trade.quantity
    
#     try:
#         # 트랜잭션 시작
#         await db.execute("BEGIN IMMEDIATE") 
        
#         # 1. 잔액 확인
#         cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (trade.user_id,))
#         row = await cursor.fetchone()
        
#         if not row:
#             raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        
#         balance_amount = row[0]
        
#         if balance_amount < total_cost:
#             raise HTTPException(status_code=400, detail="잔액이 부족합니다.")

#         # 2. 잔액 차감
#         new_balance = balance_amount - total_cost
#         await db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, trade.user_id))

#         # 3. 주식 보유량 업데이트
#         cursor = await db.execute("SELECT quantity, average_price FROM holdings WHERE user_id = ? AND company_name = ?", (trade.user_id, trade.company_name))
#         holding = await cursor.fetchone()
        
#         if holding:
#             # 추가 매수
#             old_qty, old_avg = holding
#             new_qty = old_qty + trade.quantity
#             new_avg = ((old_qty * old_avg) + total_cost) / new_qty
#             await db.execute("UPDATE holdings SET quantity = ?, average_price = ? WHERE user_id = ? AND company_name = ?", (new_qty, new_avg, trade.user_id, trade.company_name))
#         else:
#             # 신규 매수
#             await db.execute("INSERT INTO holdings (user_id, company_name, quantity, average_price) VALUES (?, ?, ?, ?)", (trade.user_id, trade.company_name, trade.quantity, trade.price))

#         await db.commit()
#         try:   
#             # 2. '첫 주식 매수' 퀘스트 체크
#             await check_quest(trade.user_id, "trade_first")
#         except Exception as e:
#             print(f"⚠️ 보상 지급 중 에러 발생: {e}")

#         return {"message": "매수 체결 완료!", "balance": new_balance}

#     except Exception as e:
#         await db.rollback()
#         raise e

#         # 4. 거래 원장(Ledger) 기록
#         await db.execute("""
#             INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
#             VALUES (?, 'BUY', ?, ?, ?)
#         """, (trade.user_id, -total_cost, new_balance, f"{trade.company_name} {trade.quantity}주 매수"))
        
#         # 승인 (Commit)
#         await db.commit()
        
#         return {
#             "status": "success", 
#             "message": f"{trade.company_name} 매수 성공!", 
#             "balance": new_balance,
#             "holdings": {"company": trade.company_name, "quantity": trade.quantity}
#         }

#     except Exception as e:
#         await db.rollback()
#         raise HTTPException(status_code=500, detail=f"거래 실패: {str(e)}")

# 4. 내 정보(잔액) 조회 API
@router.get("/user/{user_id}")
async def get_user_info(user_id: int, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [지갑 조회]
    앱 메인화면에 띄워줄 유저의 현재 잔액과 보유 주식 정보를 가져옵니다.
    """
    # 1. 잔액 조회
    cursor = await db.execute("SELECT username, balance FROM users WHERE id = ?", (user_id,))
    user_row = await cursor.fetchone()
    
    if not user_row:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
        
    # 2. 보유 주식 조회 (현재 가지고 있는 것만)
    cursor = await db.execute("""
        SELECT company_name, quantity, average_price 
        FROM holdings 
        WHERE user_id = ? AND quantity > 0
    """, (user_id,))
    holdings_rows = await cursor.fetchall()
    
    return {
        "username": user_row[0],
        "balance": user_row[1],
        "holdings": [dict(row) for row in holdings_rows]
    }

# 5. 보상 지급 API (퀘스트, 배당금 등)
class RewardRequest(BaseModel):
    user_id: int
    amount: float
    description: str

@router.post("/reward")
async def give_reward(reward: RewardRequest, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [보상 지급 시스템]
    - 특정 유저에게 돈을 지급합니다.
    - 퀘스트 완료, 레벨업 축하금, 배당금 지급 등에 사용됩니다.
    - 거래 장부(Ledger)에 'REWARD' 타입으로 기록됩니다.
    """
    try:
        await db.execute("BEGIN IMMEDIATE")

        # 1. 유저 존재 확인 및 현재 잔액 조회
        cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (reward.user_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
            
        balance = row[0]
        
        # 2. 잔액 증가 (더하기)
        new_balance = balance + reward.amount
        await db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, reward.user_id))

        # 3. 거래 원장(Ledger)에 기록 (돈의 출처 남기기)
        await db.execute("""
            INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
            VALUES (?, 'REWARD', ?, ?, ?)
        """, (reward.user_id, reward.amount, new_balance, reward.description))

        await db.commit()

        return {
            "status": "success",
            "message": f"보상 지급 완료: {reward.amount}원",
            "balance": new_balance,
            "reason": reward.description
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"보상 지급 실패: {str(e)}")


# 6. 주식 매도 API (Sell)
# @router.post("/sell")
# async def sell_stock(trade: TradeRequest, db: aiosqlite.Connection = Depends(get_db_connection)):
#     """
#     [매도 트랜잭션]
#     1. 보유 주식 확인
#     2. 주식 차감
#     3. 잔액 증가
#     4. 거래 장부 기록 (transactions 테이블)
#     5. 경험치 및 퀘스트 보상 지급 (New!)
#     """
#     total_income = trade.price * trade.quantity
    
#     try:
#         await db.execute("BEGIN IMMEDIATE")

#         # 1. 내 주식고(Holdings) 확인
#         cursor = await db.execute("""
#             SELECT quantity, average_price 
#             FROM holdings 
#             WHERE user_id = ? AND company_name = ?
#         """, (trade.user_id, trade.company_name))
        
#         holding = await cursor.fetchone()
        
#         # 주식이 아예 없거나, 팔려는 개수보다 적게 가지고 있다면?
#         if not holding or holding[0] < trade.quantity:
#             raise HTTPException(status_code=400, detail="매도할 주식이 부족합니다.")

#         current_qty = holding[0]
        
#         # 2. 주식 수량 차감
#         new_qty = current_qty - trade.quantity
        
#         await db.execute("""
#             UPDATE holdings SET quantity = ? 
#             WHERE user_id = ? AND company_name = ?
#         """, (new_qty, trade.user_id, trade.company_name))

#         # 3. 유저 잔액 증가 (돈 받기)
#         cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (trade.user_id,))
#         row = await cursor.fetchone()
        
#         if not row:
#             raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

#         balance = row[0]
#         new_balance = balance + total_income
        
#         await db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, trade.user_id))

#         # 4. 거래 원장(Ledger) 기록
#         await db.execute("""
#             INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description)
#             VALUES (?, 'SELL', ?, ?, ?)
#         """, (trade.user_id, total_income, new_balance, f"{trade.company_name} {trade.quantity}주 매도"))

#         await db.commit()
        
#         try:
#             await check_quest(trade.user_id, "trade_sell_first")
            
#         except Exception as e:
#             print(f"⚠️ 보상 지급 중 에러 발생: {e}")

#         return {
#             "status": "success",
#             "message": f"{trade.company_name} {trade.quantity}주 매도 완료!",
#             "balance": new_balance,
#             "holdings": {"company": trade.company_name, "remaining_quantity": new_qty}
#         }

#     except HTTPException as he:
#         await db.rollback()
#         raise he
#     except Exception as e:
#         await db.rollback()
#         raise HTTPException(status_code=500, detail=f"매도 실패: {str(e)}")


# 7. 지정가 주문 시스템 (Limit Order)

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
async def place_order(req: OrderRequest):
    # 1. 기본 설정
    target_ticker = req.ticker if req.ticker else req.company_name
    side = req.side.upper() if req.side else "BUY"

    async with aiosqlite.connect("DB_PATH", timeout=30.0) as db:
        db.row_factory = aiosqlite.Row

        try:
            # 2. 현재가 조회
            current_market_price = None
            try:
                # 1차 시도: 원래 있던 stocks 테이블에서 기호(symbol)로 찾기
                cursor = await db.execute("SELECT current_price FROM stocks WHERE symbol = ?", (target_ticker,))
                row = await cursor.fetchone()
                if row: current_market_price = row[0]
            except Exception:
                pass

            # 2차 시도: stocks에 없다면 혹시 companies 테이블에 있을까?
            if current_market_price is None:
                try:
                    cursor = await db.execute("SELECT current_price FROM companies WHERE ticker = ? OR symbol = ?", (target_ticker, target_ticker))
                    row = await cursor.fetchone()
                    if row: current_market_price = row[0]
                except Exception:
                    pass

            if current_market_price is None:
                print(f"⚠️ [경고] DB에서 {target_ticker}의 가격을 못 찾았습니다. 유저 입력가({req.price}원)로 즉시 체결시킵니다.")
                current_market_price = req.price

            print(f"▶️ [주문 점검 완료] 대상: {target_ticker}, 현재가: {current_market_price}, 입력가: {req.price}")


            # 3. 체결 조건 계산 (진짜 주식시장 로직 반영)
            is_immediate_fill = False
            
            if current_market_price:
                if req.order_type == "MARKET":
                    is_immediate_fill = True
                    req.price = current_market_price
                else: # 지정가(LIMIT)일 경우
                    if side == "BUY":
                        # 내가 사려는 가격이 현재가보다 같거나 더 비싸면 -> 싼 현재가로 즉시 득템!
                        if req.price >= current_market_price:
                            is_immediate_fill = True
                            req.price = current_market_price 
                    elif side == "SELL":
                        # 내가 팔려는 가격이 현재가보다 같거나 더 싸면 -> 비싼 현재가로 즉시 처분!
                        if req.price <= current_market_price:
                            is_immediate_fill = True
                            req.price = current_market_price

            # 자산 선 차감 로직 (미체결이어도 돈/주식 먼저 뺌)
            total_amount = req.price * req.quantity
            
            if side == "BUY":
                # 현금 확인
                cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (req.user_id,))
                user = await cursor.fetchone()
                if not user or user['balance'] < total_amount:
                    return {"success": False, "msg": "현금이 부족합니다."}
                
                # 돈을 먼저 뺍니다! (PENDING 상태여도 차감됨)
                await db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_amount, req.user_id))

            elif side == "SELL":
                # 주식 확인
                cursor = await db.execute("SELECT quantity FROM holdings WHERE user_id = ? AND company_name = ?", (req.user_id, target_ticker))
                holding = await cursor.fetchone()
                if not holding or holding['quantity'] < req.quantity:
                    return {"success": False, "msg": "보유 주식이 부족합니다."}
                
                # 주식을 먼저 뺍니다!
                await db.execute("UPDATE holdings SET quantity = quantity - ? WHERE user_id = ? AND company_name = ?", (req.quantity, req.user_id, target_ticker))


            # 5. 즉시 체결(FILLED) 시 후처리 (이미 뺀 자산 말고, 받을 자산만 지급)
            status = "PENDING"
            msg = "주문이 접수되었습니다. (미체결)"

            if is_immediate_fill:
                if side == "BUY":
                    # 돈은 이미 뺐으니 주식만 넣어줌
                    cursor = await db.execute("SELECT quantity FROM holdings WHERE user_id = ? AND company_name = ?", (req.user_id, target_ticker))
                    holding = await cursor.fetchone()
                    if holding:
                        await db.execute("UPDATE holdings SET quantity = quantity + ? WHERE user_id = ? AND company_name = ?", (req.quantity, req.user_id, target_ticker))
                    else:
                        await db.execute("INSERT INTO holdings (user_id, company_name, quantity, average_price) VALUES (?, ?, ?, ?)", (req.user_id, target_ticker, req.quantity, req.price))
                
                elif side == "SELL":
                    # 주식은 이미 뺐으니 돈만 넣어줌
                    await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_amount, req.user_id))

                status = "FILLED"
                msg = "즉시 체결 완료!"

            # 6. 주문 기록 저장
            await db.execute("""
                INSERT INTO orders (user_id, company_name, order_type, price, quantity, status, game_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (req.user_id, target_ticker, side, req.price, req.quantity, status, req.game_date))
            
            order_id = cursor.lastrowid
            await db.commit()
            
            return {"success": True, "status": status, "msg": msg, "order_id": order_id}

        except Exception as e:
            print(f"🔥 주문 오류: {e}")
            return {"success": False, "msg": f"서버 오류: {str(e)}"}

@router.get("/orders/{user_id}")
async def get_my_orders(user_id: int, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [내 주문 내역 조회] 
    전체 상태(FILLED, PENDING, CANCELLED)를 모두 가져와야 체결 감시가 가능합니다.
    """
    cursor = await db.execute("""
        SELECT id, company_name, order_type, price, quantity, created_at, status
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC
        LIMIT 20
    """, (user_id,))
    
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

@router.delete("/order/{order_id}")
async def cancel_order(order_id: int, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [주문 취소 - 디버깅 모드]
    서버가 보는 실제 데이터를 터미널에 출력합니다.
    """
    print(f"\n🔍 [주문 취소 시도] 요청된 주문 ID: {order_id}")
    
    try:
        await db.execute("BEGIN IMMEDIATE")
        
        # 1. 주문 조회
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        columns = [description[0] for description in cursor.description]
        row = await cursor.fetchone()
        
        if not row:
            print(f"❌ [오류] ID {order_id}번 주문이 DB에 아예 없습니다.")
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
            
        # 데이터를 딕셔너리로 만듦 (안전장치)
        order = dict(zip(columns, row))
        
        print(f"📄 [DB 데이터 확인] {order}")
        print(f"🧐 [상태 점검] DB에 저장된 상태: '{order['status']}'")

        # 2. 상태 확인 (공백 제거 후 비교)
        current_status = order['status'].strip()
        
        if current_status != 'PENDING':
            print(f"🚫 [거절] 상태가 PENDING이 아니라서 취소 불가. (현재: {current_status})")
            raise HTTPException(status_code=400, detail=f"취소 불가: 현재 상태가 '{current_status}' 입니다.")
            
        # 3. 환불 절차
        user_id = order['user_id']
        price = order['price']
        quantity = order['quantity']
        
        if order['order_type'] == 'BUY':
            refund = price * quantity
            await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (refund, user_id))
            print(f"💰 [환불] 유저 {user_id}에게 {refund}원 환불 완료")
            
        elif order['order_type'] == 'SELL':
            await db.execute("UPDATE holdings SET quantity = quantity + ? WHERE user_id = ? AND company_name = ?", (quantity, user_id, order['company_name']))
            print(f"📦 [반환] 유저 {user_id}에게 {order['company_name']} {quantity}주 반환 완료")
            
        # 4. 상태 변경
        await db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
        await db.commit()
        
        print("✅ [성공] 주문 취소 및 환불 완료\n")
        return {"status": "success", "message": "주문이 취소되었습니다."}
        
    except HTTPException as he:
        await db.rollback()
        raise he
    except Exception as e:
        await db.rollback()
        print(f"🔥 [시스템 에러] {str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 에러: {str(e)}")
    
# 테스트용 강제 체결 API (나중에 자동화될 예정)
@router.post("/process_orders")
async def process_market_price_change(company_name: str, current_price: float, db: aiosqlite.Connection = Depends(get_db_connection)):
    """
    [체결 엔진 시뮬레이션]
    특정 종목의 현재 가격이 변했다고 가정하고, 조건이 맞는 대기 주문을 체결시킵니다.
    - 매수 주문: 지정가 >= 현재가 (싸게 샀으니 이득, 체결)
    - 매도 주문: 지정가 <= 현재가 (비싸게 팔았으니 이득, 체결)
    """
    processed_count = 0
    
    try:
        await db.execute("BEGIN IMMEDIATE")
        
        # 1. 체결 가능한 매수 주문 찾기 (내가 건 가격보다 현재가가 싸거나 같으면 체결)
        cursor = await db.execute("""
            SELECT id, user_id, quantity, price FROM orders 
            WHERE company_name = ? AND order_type = 'BUY' AND status = 'PENDING' AND price >= ?
        """, (company_name, current_price))
        buy_orders = await cursor.fetchall()
        
        for order in buy_orders:
            # 주식 지급
            h_cursor = await db.execute("SELECT quantity, average_price FROM holdings WHERE user_id = ? AND company_name = ?", (order['user_id'], company_name))
            holding = await h_cursor.fetchone()
            
            if holding:
                # 평단가 갱신 로직 (생략 가능하나 넣으면 좋음)
                new_qty = holding['quantity'] + order['quantity']
                new_avg = ((holding['quantity'] * holding['average_price']) + (order['quantity'] * order['price'])) / new_qty
                await db.execute("UPDATE holdings SET quantity = ?, average_price = ? WHERE user_id = ? AND company_name = ?", (new_qty, new_avg, order['user_id'], company_name))
            else:
                await db.execute("INSERT INTO holdings (user_id, company_name, quantity, average_price) VALUES (?, ?, ?, ?)", (order['user_id'], company_name, order['quantity'], order['price']))
            
            # 주문 완료 처리
            await db.execute("UPDATE orders SET status = 'FILLED' WHERE id = ?", (order['id'],))
            
            # 거래 기록 남기기
            await db.execute("INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description) VALUES (?, 'BUY', ?, 0, ?)", 
                             (order['user_id'], -(order['price'] * order['quantity']), f"{company_name} {order['quantity']}주 지정가 체결"))
            processed_count += 1

        # 2. 체결 가능한 매도 주문 찾기 (내가 건 가격보다 현재가가 비싸거나 같으면 체결)
        cursor = await db.execute("""
            SELECT id, user_id, quantity, price FROM orders 
            WHERE company_name = ? AND order_type = 'SELL' AND status = 'PENDING' AND price <= ?
        """, (company_name, current_price))
        sell_orders = await cursor.fetchall()
        
        for order in sell_orders:
            # 판매 대금 지급
            income = order['price'] * order['quantity']
            await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (income, order['user_id']))
            
            # 주문 완료 처리
            await db.execute("UPDATE orders SET status = 'FILLED' WHERE id = ?", (order['id'],))
            
            # 거래 기록
            await db.execute("INSERT INTO transactions (user_id, transaction_type, amount, balance_after, description) VALUES (?, 'SELL', ?, 0, ?)",
                                (order['user_id'], income, f"{company_name} {order['quantity']}주 지정가 체결"))
            processed_count += 1
            
        await db.commit()
        return {"status": "success", "message": f"{processed_count}건의 주문이 체결되었습니다."}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, str(e))
    
# 레벨 체크 디펜던시
async def verify_level_5(db: aiosqlite.Connection = Depends(get_db_connection)):
    user_id = 1
    cursor = await db.execute("SELECT level FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    
    current_level = row[0] if row else 1
    
    if current_level < 5:
        raise HTTPException(
            status_code=403, 
            detail=f"🔒 호가창은 LV.5부터 이용 가능합니다. (현재: LV.{current_level})"
        )
    return True

# 호가창 API
@router.get("/orderbook/{company_name}")
async def get_order_book(
    company_name: str, 
    is_authorized: bool = Depends(verify_level_5)
):
    """
    [호가창 조회]
    레벨 5 이상인 유저만 주식의 매수/매도 대기 물량을 볼 수 있습니다.
    """
    return {
        "company": company_name,
        "asks": [{"price": 81000, "qty": 10}, {"price": 82000, "qty": 50}], # 팔려는 사람
        "bids": [{"price": 79000, "qty": 20}, {"price": 78000, "qty": 100}] # 살려는 사람
    }

@router.get("/orders/all/{user_id}")
async def get_all_orders_all(user_id: int, db: aiosqlite.Connection = Depends(get_db_connection)):
    cursor = await db.execute("""
        SELECT id, company_name, order_type as side, price, quantity, status, game_date, created_at
        FROM orders 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    """, (user_id,))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]