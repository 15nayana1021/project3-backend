from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlalchemy import desc, asc, func
from sqlalchemy.orm import Session
from database import SessionLocal, DBCompany, DBTrade, DBNews, DBAgent, DBDiscussion
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
import os

# 유저님의 핵심 엔진 및 멘토 임포트
from core.team_market_engine import MarketEngine
from models.domain_models import Order, OrderSide, OrderType
from core.mentor_brain import generate_all_mentors_advice, chat_with_mentor

router = APIRouter()
engine = MarketEngine()

# --- [Helper] DB 세션 및 시간 동기화 ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_sim_time(db: Session):
    """
    시뮬레이션의 '가짜 현재 시간'을 가져옵니다.
    """
    last_trade = db.query(DBTrade).order_by(desc(DBTrade.timestamp)).first()
    if last_trade:
        return last_trade.timestamp
    return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

# --- [Schemas] 요청 데이터 검증 ---

class CommunityPostRequest(BaseModel):
    author: str
    content: str
    ticker: str
    sentiment: str

class OrderRequest(BaseModel):
    ticker: str
    side: str  # "BUY" or "SELL"
    price: float
    quantity: int

class UserInitRequest(BaseModel):
    username: str

class ChatRequest(BaseModel):
    agent_type: str
    message: str

# --- [API Endpoints] ---

# 1. 기업 목록 조회 (등락률 + 거래량 계산 로직)
@router.get("/api/companies")
def get_companies(db: Session = Depends(get_db)):
    companies = db.query(DBCompany).all()
    sim_now = get_current_sim_time(db)
    sim_today_start = sim_now.replace(hour=9, minute=0, second=0, microsecond=0)
    
    result = []
    for comp in companies:
        first_trade = db.query(DBTrade).filter(
            DBTrade.ticker == comp.ticker,
            DBTrade.timestamp >= sim_today_start
        ).order_by(asc(DBTrade.timestamp)).first()
        
        change_rate = 0
        if first_trade and first_trade.price > 0:
            change_rate = ((comp.current_price - first_trade.price) / first_trade.price) * 100
        
        total_volume = db.query(func.sum(DBTrade.quantity)).filter(
            DBTrade.ticker == comp.ticker,
            DBTrade.timestamp >= sim_today_start
        ).scalar() or 0
        
        result.append({
            "ticker": comp.ticker,
            "name": comp.name,
            "sector": comp.sector,
            "current_price": comp.current_price,
            "change_rate": round(change_rate, 2),
            "volume": int(total_volume)
        })
    return result

# 2. 특정 기업 차트 데이터
@router.get("/api/chart/{ticker}")
def get_chart(ticker: str, limit: int = 3000, db: Session = Depends(get_db)): 
    trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(limit).all()
    return [{"time": t.timestamp.isoformat(), "price": t.price} for t in trades][::-1]

# 5. 커뮤니티 (기능 유지)
@router.get("/api/community/global")
def get_global_community_posts(db: Session = Depends(get_db)):
    posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == 'GLOBAL').order_by(desc(DBDiscussion.created_at)).limit(50).all()
    return [{"id": p.id, "author": p.agent_id, "content": p.content, "sentiment": p.sentiment, "time": p.created_at.strftime("%H:%M")} for p in posts]

@router.get("/api/community/{ticker}")
def get_stock_community(ticker: str, db: Session = Depends(get_db)):
    posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == ticker).order_by(desc(DBDiscussion.id)).limit(20).all()
    return [{"id": p.id, "author": p.agent_id, "content": p.content, "sentiment": p.sentiment, "time": p.created_at.strftime("%H:%M")} for p in posts]

@router.post("/api/community")
def create_community_post(req: CommunityPostRequest, db: Session = Depends(get_db)):
    sim_now = get_current_sim_time(db)
    try:
        new_post = DBDiscussion(ticker=req.ticker, agent_id=req.author, content=req.content, sentiment=req.sentiment, created_at=sim_now)
        db.add(new_post)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# 7. 멘토 및 챗봇 (기능 유지)
@router.get("/api/advice/{ticker}")
async def get_mentor_advice(ticker: str, x_user_id: str = Header("USER_01"), db: Session = Depends(get_db)):
    try: return await generate_all_mentors_advice(db, ticker, x_user_id)
    except Exception as e: return {"error": str(e)}

@router.post("/api/chat")
async def handle_chat(req: ChatRequest):
    try:
        reply = await chat_with_mentor(req.agent_type, req.message)
        return {"reply": reply}
    except Exception: return {"reply": "챗봇 서비스 일시 점검 중입니다."}