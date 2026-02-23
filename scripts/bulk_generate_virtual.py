import os
import sys
import asyncio
import time
import random
import sqlite3
import json

# 1. 경로 설정
current_file = os.path.abspath(__file__)
scripts_folder = os.path.dirname(current_file)
backend_root = os.path.dirname(scripts_folder)

if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

os.chdir(backend_root)

# 2. 필요한 모듈 임포트
try:
    from core.agent_service import StockAgentService
    from database import DB_NAME 
except ImportError:
    DB_PATH = "/home/site/wwwroot/stock_game.db" if os.getenv("WEBSITE_HOSTNAME") else "stock_game.db"
    from core.agent_service import StockAgentService

# 가상 뉴스 전용 10개 기업 리스트
TARGET_COMPANIES = [
    {"name": "재웅시스템", "sector": "전자", "desc": "시스템 반도체 설계"},
    {"name": "에이펙스테크", "sector": "전자", "desc": "로봇 및 자동화 설비"},
    {"name": "소현컴퍼니", "sector": "IT", "desc": "웹 플랫폼 및 클라우드"},
    {"name": "넥스트데이터", "sector": "IT", "desc": "데이터센터 인프라"},
    {"name": "진호랩", "sector": "바이오", "desc": "mRNA 신약 개발"},
    {"name": "상은테크놀로지", "sector": "바이오", "desc": "의료 정밀 기기"},
    {"name": "인사이트애널리틱스", "sector": "바이오", "desc": "AI 의료 진단"},
    {"name": "선우솔루션", "sector": "금융", "desc": "핀테크 보안"},
    {"name": "퀀텀디지털", "sector": "금융", "desc": "알고리즘 트레이딩"},
    {"name": "예진캐피탈", "sector": "금융", "desc": "벤처 투자(VC)"}
]

VIRTUAL_PRESS = ["스토키 일보", "매일경제 AI", "한경 인사이트", "블록체인 뉴스", "Stocky Daily", "월스트리트 찌라시"]

def save_direct_to_db(company_name, category, news_list):
    """
    stock_game.db에 뉴스를 저장합니다.
    (테이블 강제 생성 + 점수 음수 보정 + 언론사 저장 기능 포함)
    """
    db_path = os.path.join(backend_root, DB_NAME)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 테이블이 없으면 만드는 안전장치
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                title TEXT,
                content TEXT,
                summary TEXT,
                sentiment TEXT,
                impact_score INTEGER,
                published_at TEXT,
                company_name TEXT, 
                category TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 컬럼 확인 및 추가 (기존 DB에 새 칸 뚫기)
        cursor.execute("PRAGMA table_info(news)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'company_name' not in columns:
            cursor.execute("ALTER TABLE news ADD COLUMN company_name TEXT")
        if 'category' not in columns:
            cursor.execute("ALTER TABLE news ADD COLUMN category TEXT")
        if 'source' not in columns:
            cursor.execute("ALTER TABLE news ADD COLUMN source TEXT")
            
        for news in news_list:
            # 3. 점수 및 감성 보정
            raw_score = news.get('impact_score', 0)
            sentiment = news.get('sentiment', 'neutral').lower()
            
            final_score = abs(raw_score) 
            if 'negative' in sentiment:
                final_score = -final_score

            # 4. 언론사 랜덤 선택 (가상 뉴스니까 VIRTUAL_PRESS 중 하나 뽑기)
            source_name = news.get('source', random.choice(VIRTUAL_PRESS))

            # 5. 데이터 삽입 (source 포함)
            cursor.execute("""
                INSERT INTO news (
                    company_name, category, title, content, 
                    summary, sentiment, impact_score, 
                    ticker, source, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                company_name, 
                category, 
                news.get('title'), 
                news.get('content'),
                news.get('summary'), 
                sentiment,     
                final_score,
                company_name,
                source_name
            ))
            
        conn.commit()
        print(f" -> ✅ 저장 완료 (감성: {sentiment}, 점수: {final_score}, 출처: {source_name})")
        
    except Exception as e:
        print(f" -> ❌ 저장 실패: {e}")
    finally:
        conn.close()

def run_bulk_generation():
    print(f"📂 사용 중인 DB: {DB_NAME}") 
    agent = StockAgentService(mode="virtual")
    
    # 🧹 [안전장치 1] 시작하자마자 기존 뉴스를 싹 지워버립니다.
    # try:
    #     db_path = os.path.join(backend_root, DB_NAME)
    #     conn = sqlite3.connect(db_path)
    #     cursor = conn.cursor()
    #     cursor.execute("DELETE FROM news") 
    #     conn.commit()
    #     conn.close()
    #     print("🧹 [초기화 완료] 기존의 모든 뉴스를 삭제했습니다.")
    # except Exception as e:
    #     print(f"⚠️ 초기화 중 경고: {e}")

    print("\n🏢 [Money Quest] 기업당 10건의 최신 뉴스 생성을 시작합니다...\n")

    for comp in TARGET_COMPANIES:
        print(f"✍️ {comp['name']} 뉴스 생성 중...", end="", flush=True)

        result = agent.analyze_stock_news(comp['name'], mode="virtual", count=10, company_desc=comp.get('desc', '')) 
        
        if isinstance(result, list) and len(result) > 0:
            final_result = result 
            
            for news_item in final_result:
                news_item['source'] = random.choice(VIRTUAL_PRESS)

            save_direct_to_db(comp['name'], comp['sector'], final_result)
        else:
            print(f" -> ❌ 생성 실패")
            
        time.sleep(1)

    print("\n✨ 모든 작업 완료!")

if __name__ == "__main__":
    run_bulk_generation()