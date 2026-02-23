from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from pydantic import BaseModel
from urllib.parse import unquote
from collections import defaultdict
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
import os

# 💡 1. DB 관련 설정 (database.py에서 가져옴)
# db_engine으로 이름을 바꿔서 시뮬레이션 엔진과 충돌을 피합니다.
from database import engine as db_engine, init_db, SessionLocal, get_db, DBCompany, DBAgent

# 💡 2. 시뮬레이션 관련 설정 (main_simulation.py에서 가져옴)
# 모듈 자체를 import하고, 엔진 이름은 sim_engine으로 바꿉니다.
import main_simulation
from main_simulation import market_engine as sim_engine, run_simulation_loop

from routers import trade, social, news
from team_api import router as team_router
from core.mentor_brain import chat_with_mentor

# [전역 설정]
TARGET_TICKERS = [
    "삼송전자", "재웅시스템", "에이펙스테크",      # 전자
    "마이크로하드", "소현컴퍼니", "넥스트데이터", # IT
    "진호랩", "상은테크놀로지", "인사이트애널리틱스",    # 바이오
    "선우솔루션", "퀀텀디지털", "예진캐피탈" # 금융
]

INITIAL_PRICES = {
    "삼송전자": 172000, "재웅시스템": 45000, "에이펙스테크": 28000,
    "마이크로하드": 580000, "소현컴퍼니": 62000, "넥스트데이터": 34000,
    "진호랩": 89000, "상은테크놀로지": 54000, "인사이트애널리틱스": 41000,
    "선우솔루션": 22000, "퀀텀디지털": 115000, "예진캐피탈": 198000
}

COMPANY_CATEGORIES = {
    "삼송전자": "전자", "재웅시스템": "전자", "에이펙스테크": "전자",
    "마이크로하드": "IT", "소현컴퍼니": "IT", "넥스트데이터": "IT",
    "진호랩": "바이오", "상은테크놀로지": "바이오", "인사이트애널리틱스": "바이오",
    "선우솔루션": "금융", "퀀텀디지털": "금융", "예진캐피탈": "금융"
}

TICKER_MAP = {
    "삼송전자": "SS011", "재웅시스템": "JW004", "에이펙스테크": "AT010",
    "마이크로하드": "MH012", "소현컴퍼니": "SH001", "넥스트데이터": "ND008",
    "진호랩": "JH005", "상은테크놀로지": "SE002", "인사이트애널리틱스": "IA009",
    "선우솔루션": "SW006", "퀀텀디지털": "QD007", "예진캐피탈": "YJ003"
}

# 🏆 [랭킹 점수판] 
hot_scores = {ticker: 0 for ticker in TARGET_TICKERS}

# 초기 데이터
current_news_display = "장 시작 준비 중..."
price_history = {ticker: [] for ticker in TARGET_TICKERS}
current_mentor_comments = {ticker: [] for ticker in TARGET_TICKERS}

# 시뮬레이션 엔진 
async def simulate_market_background():
    print("🚀 [시스템] 유저 주문 모니터링 시작 (PostgreSQL 버전)")
    # (추후 PostgreSQL 버전의 체결 로직이 여기에 들어갑니다)
    pass

def seed_database():
    with SessionLocal() as db:
        print("🌱 [시스템] DB 데이터를 보존하며 INITIAL_PRICES를 동기화합니다...")
        
        for name, price in INITIAL_PRICES.items():
            correct_ticker = TICKER_MAP.get(name, name)
            company = db.query(DBCompany).filter(DBCompany.name == name).first()
            
            if company:
                company.ticker = correct_ticker
                company.current_price = float(price)
            else:
                new_comp = DBCompany(
                    ticker=correct_ticker, name=name, 
                    current_price=float(price), change_rate=0.0
                )
                db.add(new_comp)
        
        db.commit()

        if db.query(DBAgent).count() == 0:
            print("🤖 [시스템] AI 에이전트 30명을 시장에 투입합니다...")
            agents = [
                DBAgent(agent_id=f"Agent_Bot_{i}", cash_balance=100000000, portfolio={}, psychology={})
                for i in range(1, 31)
            ]
            db.add_all(agents)
            db.commit()
            
        print("✅ [시스템] 주식 가격 및 영어 코드(Ticker) 동기화 완료!")

# [FastAPI 앱 설정]
@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 초기화 및 데이터 적재
    init_db()
    seed_database() 
    
    # 이제 main_simulation 모듈을 정상적으로 인식합니다.
    main_simulation.running = True
    asyncio.create_task(run_simulation_loop())
    print("🚀 [시스템] 시뮬레이션과 서버가 정상 가동됩니다!")
    
    yield 

    print("🛑 [시스템] 서버 종료 신호 감지! 시뮬레이션을 중단합니다.")
    main_simulation.running = False
    await asyncio.sleep(1)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://witty-bush-04d128e00.1.azurestaticapps.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trade.router)
app.include_router(social.router, prefix="/api/social", tags=["Social & Ranking"])
app.include_router(news.router)
app.include_router(team_router, prefix="/team", tags=["Team API"])

@app.get("/api/market-data")
async def get_market_data(ticker: str = "삼송전자"):
    # engine -> sim_engine으로 변경
    if ticker not in sim_engine.companies:
        return {"error": "Stock not found", "ticker": ticker}
    
    comp = sim_engine.companies[ticker]
    book = sim_engine.order_books.get(ticker, {"BUY": [], "SELL": []})
    
    buy_orders = [o.dict() for o in book["BUY"][:5]]
    sell_orders = [o.dict() for o in book["SELL"][:5]]

    if ticker in hot_scores:
        hot_scores[ticker] += 1

    return {
        "ticker": ticker,     
        "name": ticker,
        "price": comp.current_price,
        "news": current_news_display,
        "history": price_history.get(ticker, []),
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "mentors": current_mentor_comments.get(ticker, [])
    }

@app.get("/api/stocks")
def get_all_stocks(db: Session = Depends(get_db)):
    try:
        companies = db.query(DBCompany).all()
        result = []
        for c in companies:
            result.append({
                "ticker": str(c.ticker) if c.ticker else "UNKNOWN",
                "name": str(c.name) if c.name else "알 수 없음",
                "current_price": int(c.current_price) if c.current_price is not None else 0,
                "change_rate": float(c.change_rate) if hasattr(c, 'change_rate') and c.change_rate is not None else 0.0
            })
        return result
    except Exception as e:
        print(f"❌ 목록 로딩 에러: {e}")
        return []

class LoginRequest(BaseModel):
    nickname: str

@app.post("/users/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    """닉네임으로 로그인 (PostgreSQL 버전)"""
    try:
        # 유저 존재 여부 확인
        user_query = text("SELECT id FROM users WHERE username = :nickname")
        user = db.execute(user_query, {"nickname": request.nickname}).fetchone()
        
        if not user:
            # 새 유저 생성 및 100만원 지급
            insert_query = text("INSERT INTO users (username, balance) VALUES (:nickname, 1000000) RETURNING id")
            new_user_id = db.execute(insert_query, {"nickname": request.nickname}).scalar()
            db.commit()
            real_user_id = new_user_id
        else:
            real_user_id = user[0]
            
        return {
            "success": True, 
            "message": f"Welcome {request.nickname}!", 
            "user_id": real_user_id
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}

class ChatRequest(BaseModel):
    agent_type: str
    message: str

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        reply = await chat_with_mentor(req.agent_type, req.message)
        return {"reply": reply}
    except Exception as e:
        print(f"❌ 챗봇 응답 에러: {e}")
        return {"reply": "앗, 뇌 회로에 잠시 과부하가 왔어요! 조금만 이따가 다시 질문해주세요."}

@app.get("/users/me/portfolio")
def get_my_portfolio(user_id: str = "1", db: Session = Depends(get_db)): 
    """자산 정보 조회 (PostgreSQL 버전)"""
    # 1. 유저 조회
    user_query = text("SELECT id, username, balance FROM users WHERE username = :uid OR id::text = :uid")
    user = db.execute(user_query, {"uid": user_id}).fetchone()
    
    if not user:
        return {
            "name": "알 수 없음", "cash_balance": 0, "total_asset_value": 0, "portfolio": []
        }
    
    real_db_id = user[0] 
    name = user[1]
    cash = user[2]

    # 2. 보유 주식 조회
    portfolio = []
    total_stock_value = 0
    
    holdings_query = text("SELECT company_name, quantity, average_price FROM holdings WHERE user_id = :uid")
    holdings = db.execute(holdings_query, {"uid": real_db_id}).fetchall()
    
    for row in holdings:
        ticker = row[0]
        qty = row[1]
        avg_price = row[2]
        
        # 현재가 가져오기
        current_price = sim_engine.companies[ticker].current_price if hasattr(sim_engine, 'companies') and ticker in sim_engine.companies else avg_price
        profit_rate = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
        
        portfolio.append({
            "ticker": ticker, "quantity": qty, "current_price": int(current_price),
            "profit_rate": round(profit_rate, 2), "average_price": int(avg_price)
        })
        total_stock_value += (current_price * qty)

    return {
        "name": name, "cash_balance": int(cash), "total_asset_value": int(cash + total_stock_value), "portfolio": portfolio
    }

@app.get("/api/stocks/{ticker}")
async def get_stock_detail(ticker: str):
    if ticker not in sim_engine.companies:
        return {"error": "Stock not found"}
    comp = sim_engine.companies[ticker]
    return {
        "ticker": ticker, "name": ticker, "sector": COMPANY_CATEGORIES.get(ticker, "Tech"), "current_price": int(comp.current_price),
    }

@app.get("/api/stocks/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "1d"):
    return price_history.get(ticker, [])

@app.get("/api/stocks/{ticker}/orderbook")
async def get_stock_orderbook(ticker: str, db: Session = Depends(get_db)):
    company = db.query(DBCompany).filter(
        or_(DBCompany.ticker == ticker, DBCompany.name == ticker)
    ).first()

    if not company:
        return {"error": "Stock not found"}

    actual_ticker = company.ticker
    current_price = int(company.current_price)
    book = sim_engine.order_books.get(actual_ticker, {"SELL": [], "BUY": []})

    ask_summary = defaultdict(int)
    for o in book.get("SELL", []):
        ask_summary[int(o["price"])] += o["quantity"]
        
    bid_summary = defaultdict(int)
    for o in book.get("BUY", []):
        bid_summary[int(o["price"])] += o["quantity"]

    asks = [{"price": p, "volume": v} for p, v in sorted(ask_summary.items())][:5]
    bids = [{"price": p, "volume": v} for p, v in sorted(bid_summary.items(), reverse=True)][:5]

    return {
        "ticker": actual_ticker, "current_price": current_price, "asks": asks, "bids": bids
    }

@app.get("/api/ranking/hot")
def get_hot_ranking(db: Session = Depends(get_db)):
    sorted_ranking = sorted(hot_scores.items(), key=lambda x: x[1], reverse=True)[:12]
    response_data = []
    
    for rank, (ticker_name, score) in enumerate(sorted_ranking, 1):
        company = db.query(DBCompany).filter(
            or_(DBCompany.ticker == ticker_name, DBCompany.name == ticker_name)
        ).first()
        
        if company:
            price = int(company.current_price) if company.current_price else 0
            change = float(company.change_rate) if hasattr(company, 'change_rate') and company.change_rate else 0.0
            name = company.name if company.name else ticker_name
            symbol = company.ticker
        else:
            price = 0; change = 0.0; name = ticker_name; symbol = ticker_name

        response_data.append({
            "rank": rank, "ticker": symbol, "name": name, "score": score,
            "current_price": price, "change_rate": round(change, 2)
        })
        
    return response_data

@app.get("/api/news")
def get_all_news(db: Session = Depends(get_db)):
    """모든 뉴스 조회 (PostgreSQL 버전)"""
    query = text("SELECT id, ticker, title, source, created_at as time FROM news ORDER BY id DESC LIMIT 20")
    result = db.execute(query).fetchall()
    return [{"id": row[0], "ticker": row[1], "title": row[2], "source": row[3], "time": row[4]} for row in result]

@app.get("/api/stocks/{ticker}/news")
def get_stock_news(ticker: str, db: Session = Depends(get_db)):
    """특정 종목 뉴스 조회 (PostgreSQL 버전)"""
    decoded_ticker = unquote(ticker)
    # ticker 또는 title에 포함된 뉴스 검색
    query = text("""
        SELECT id, ticker, title, source, created_at as time, category, content, summary 
        FROM news 
        WHERE ticker LIKE :search OR title LIKE :search
        ORDER BY id DESC LIMIT 50
    """)
    result = db.execute(query, {"search": f"%{decoded_ticker}%"}).fetchall()
    
    # 딕셔너리로 변환하여 리턴
    news_list = []
    for row in result:
        news_list.append({
            "id": row[0], "ticker": row[1], "title": row[2], "source": row[3],
            "time": row[4], "category": row[5] if len(row) > 5 else None,
            "content": row[6] if len(row) > 6 else None, "summary": row[7] if len(row) > 7 else None
        })
    return news_list

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, access_log=False)