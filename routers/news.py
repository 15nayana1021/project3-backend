from fastapi import APIRouter, HTTPException, Depends, Header, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import os

try:
    from services.gamification import gain_exp, check_quest
except ImportError:
    # 동기 함수로 변경 (SQLAlchemy 버전에 맞춤)
    def gain_exp(*args, **kwargs): pass
    def check_quest(*args, **kwargs): pass

router = APIRouter(prefix="/api/news", tags=["News"])

# 1. 뉴스 목록 조회 (회사명 필터링 포함)
@router.get("")
@router.get("/")
@router.get("/news")
def get_published_news( # 👈 async 제거
    company: str = Query(None, description="필터링할 회사 이름"),
    db: Session = Depends(get_db) # 👈 Session 사용
):
    try:
        if company:
            # 💡 PostgreSQL용 LIKE 쿼리 파라미터 적용
            query = text("""
                SELECT * FROM news 
                WHERE company_name = :company OR title LIKE :search OR summary LIKE :search
                ORDER BY id DESC 
                LIMIT 1000
            """)
            search_term = f"%{company}%"
            # 딕셔너리 형태로 파라미터 전달
            result = db.execute(query, {"company": company, "search": search_term}).fetchall()
        else:
            query = text("""
                SELECT * FROM news 
                ORDER BY id DESC 
                LIMIT 1000
            """)
            result = db.execute(query).fetchall()

        # 결과 매핑
        news_list = []
        for row in result:
            d = dict(row._mapping) # 👈 SQLAlchemy의 row 매핑 객체를 딕셔너리로 변환
            news_list.append({
                "id": d.get("id"),
                "title": d.get("title", "제목 없음"),
                "summary": d.get("summary", ""),
                "sentiment": d.get("sentiment", "neutral"),
                "impact_score": d.get("impact_score", 0),
                "category": d.get("category", "일반"),
                "source": d.get("source", "Stocky News"),
                "company_name": d.get("company_name", "미분류"), 
                "published_at": d.get("published_at", "")
            })
            
        return news_list
            
    except Exception as e:
        print(f"❌ 뉴스 목록 조회 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. 뉴스 상세 조회 API
@router.get("/{news_id}")
def get_news_detail( # 👈 async 제거
    news_id: int = Path(..., description="읽으려는 뉴스의 ID"),
    x_user_id: int = Header(1, alias="X-User-ID"),
    db: Session = Depends(get_db) # 👈 Session 사용
):
    try:
        query = text("SELECT * FROM news WHERE id = :news_id")
        result = db.execute(query, {"news_id": news_id}).fetchone()
            
        if not result:
            raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")
        
        d = dict(result._mapping)
        news_detail = {
            "id": d.get("id"),
            "title": d.get("title", "제목 없음"),
            "content": d.get("content") or d.get("summary") or "내용이 없습니다.",
            "summary": d.get("summary", ""),
            "source": d.get("source", "Stocky News"),
            "category": d.get("category", "일반"),
            "published_at": d.get("published_at", "")
        }

        # 경험치 지급 로직 (동기 함수로 가정)
        try:
            gain_exp(x_user_id, 10)
            check_quest(x_user_id, "news_read_1")
        except Exception:
            pass

        return news_detail

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 뉴스 상세 조회 에러: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")