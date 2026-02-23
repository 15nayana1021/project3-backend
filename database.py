import os
import asyncio
import aiosqlite
from datetime import datetime
from dotenv import load_dotenv

# 임포트
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = "/home/site/wwwroot/stock_game.db" if os.getenv("WEBSITE_HOSTNAME") else "stock_game.db"

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    print("⚠️ [경고] DATABASE_URL이 없어 팀원 시스템용 로컬 SQLite(team_cloud.db)를 사용합니다.")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./team_cloud.db"
elif SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite일 때와 PostgreSQL일 때의 엔진 설정을 자동으로 구분합니다.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        pool_pre_ping=True,
        pool_size=50,
        max_overflow=100,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
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

class DBNews(Base):
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
    created_at = Column(DateTime, default=datetime.utcnow)



# 뉴스 & 랭킹 & 자산 관리용 (aiosqlite)

async def get_db_connection():
    """FastAPI 라우터에서 쓸 DB 연결 생성기"""
    conn = await aiosqlite.connect(DB_PATH, timeout=30.0)
    conn.row_factory = aiosqlite.Row
    return conn



# 3. 통합 DB 초기화 함수 (main.py에서 한 번에 실행됨)
async def init_db():
    print("🛠️ 통합 데이터베이스 초기화를 시작합니다...")

    # --- 1) 팀원 DB 초기화 (SQLAlchemy 방식) ---
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ [팀원 시스템] SQLAlchemy 모델 초기화 완료")
    except Exception as e:
        print(f"❌ [팀원 시스템] 테이블 생성 실패: {e}")

    # --- 2) 사용자(내) DB 초기화 (aiosqlite 방식) ---
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;") 
        
        # 1. users 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            balance INTEGER DEFAULT 1000000,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0
        )
        """)
        try: await db.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN exp INTEGER DEFAULT 0")
        except: pass

        # 2. user_quests 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_quests (
            user_id INTEGER,
            quest_id TEXT,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            reward_amount INTEGER,
            PRIMARY KEY (user_id, quest_id)
        )
        """)
        try: await db.execute("ALTER TABLE user_quests ADD COLUMN is_completed INTEGER DEFAULT 1") 
        except: pass

        # 3. orders 테이블 업데이트 및 생성
        try: await db.execute("ALTER TABLE orders ADD COLUMN game_date TEXT")
        except: pass
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            company_name TEXT,
            order_type TEXT,
            price INTEGER,
            quantity INTEGER,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 4. holdings 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            user_id INTEGER,
            company_name TEXT,
            quantity INTEGER,
            average_price REAL,
            PRIMARY KEY (user_id, company_name)
        )
        """)

        # 5. transactions 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_type TEXT,
            amount INTEGER,
            balance_after INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 6. stocks 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            company_name TEXT,
            current_price INTEGER,
            description TEXT
        )
        """)

        # 7. news 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            title TEXT,
            content TEXT,
            summary TEXT,
            sentiment TEXT,
            impact_score INTEGER,
            source TEXT,
            published_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        try: await db.execute("ALTER TABLE news ADD COLUMN ticker TEXT")
        except: pass
        try: await db.execute("ALTER TABLE news ADD COLUMN summary TEXT")
        except: pass
        try: await db.execute("ALTER TABLE news ADD COLUMN sentiment TEXT")
        except: pass
        try: await db.execute("ALTER TABLE news ADD COLUMN published_at TEXT")
        except: pass

        # 8. quests 목록
        await db.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            quest_id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            reward_exp INTEGER
        )
        """)

        await db.commit()
        print("✅ [내 시스템] aiosqlite 로컬 테이블(stock_game.db) 초기화 완료")

if __name__ == "__main__":
    asyncio.run(init_db())