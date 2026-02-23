import os
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. 환경변수 및 엔진 설정
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    print("⚠️ [경고] DATABASE_URL이 없습니다. 로컬 SQLite를 임시로 사용합니다.")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./team_cloud.db"
elif SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,      # 👈 통신 전 연결이 살아있는지 확인! (필수)
        pool_recycle=300,        # 👈 300초(5분)마다 연결을 새것으로 교체! (필수) 
        pool_pre_ping=True,
        pool_size=50,
        max_overflow=100,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 📂 1. 팀원 시스템 모델 (기존 유지)
# ==========================================
class DBCompany(Base):
    __tablename__ = "companies"
    ticker = Column(String, primary_key=True, index=True)
    name = Column(String)
    sector = Column(String)
    current_price = Column(Float)
    change_rate = Column(Float, default=0.0)

class DBAgent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True)
    psychology = Column(JSON, default={})
    cash_balance = Column(Float, default=1000000.0)
    portfolio = Column(JSON, default={})

class DBTrade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Integer)
    buyer_id = Column(String)
    seller_id = Column(String)
    timestamp = Column(DateTime, default=datetime.now)

class DBNewsPool(Base):
    __tablename__ = "news_pool" 
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String)
    impact_score = Column(Integer)
    reason = Column(String)
    is_published = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

class DBCommunity(Base):
    __tablename__ = "community_posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    author = Column(String)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    parent_id = Column(Integer, nullable=True) 

class DBDiscussion(Base):
    __tablename__ = "stock_discussions"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    agent_id = Column(String)
    content = Column(String)
    sentiment = Column(String)
    created_at = Column(DateTime, default=datetime.now)

# ==========================================
# 📂 2. 진호 님 시스템 모델 (aiosqlite 대체!)
# ==========================================
class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True) # Postgres가 알아서 1,2,3... 번호 부여
    username = Column(String)
    password = Column(String)
    balance = Column(Integer, default=1000000)
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)

class DBUserQuest(Base):
    __tablename__ = "user_quests"
    user_id = Column(Integer, primary_key=True)
    quest_id = Column(String, primary_key=True)
    is_completed = Column(Integer, default=0)
    completed_at = Column(String)
    reward_amount = Column(Integer)

class DBOrder(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    company_name = Column(String)
    order_type = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    status = Column(String, default='PENDING')
    game_date = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class DBHolding(Base):
    __tablename__ = "holdings"
    user_id = Column(Integer, primary_key=True)
    company_name = Column(String, primary_key=True)
    quantity = Column(Integer)
    average_price = Column(Float)

class DBTransaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    transaction_type = Column(String)
    amount = Column(Integer)
    balance_after = Column(Integer)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class DBStock(Base):
    __tablename__ = "stocks"
    symbol = Column(String, primary_key=True)
    company_name = Column(String)
    current_price = Column(Integer)
    description = Column(String)

class DBNews(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String)
    title = Column(String)
    content = Column(String)
    summary = Column(String)
    sentiment = Column(String)
    impact_score = Column(Integer)
    source = Column(String)
    published_at = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class DBQuest(Base):
    __tablename__ = "quests"
    quest_id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    reward_exp = Column(Integer)

# ==========================================
# ⚙️ 3. 연결 및 초기화 함수
# ==========================================
def get_db():
    """FastAPI 라우터에서 사용할 SQLAlchemy 세션 생성기"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """통합 데이터베이스 초기화 (모든 테이블 한 번에 생성)"""
    print("🛠️ 통합 데이터베이스(PostgreSQL) 초기화를 시작합니다...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 모든 테이블(users, orders, news 등) 생성 완료!")
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    init_db()