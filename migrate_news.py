import sqlite3
import pandas as pd
from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

# .env 파일 불러오기
load_dotenv()
pg_url = os.getenv("DATABASE_URL")

try:
    print("1. 로컬 stock_game.db에서 뉴스 읽어오는 중...")
    sqlite_conn = sqlite3.connect('stock_game.db')
    news_df = pd.read_sql_query("SELECT * FROM news", sqlite_conn)

    print("2. 클라우드 PostgreSQL 연결 및 구조 확인 중...")
    pg_engine = create_engine(pg_url)
    
    # 💡 클라우드 DB(PostgreSQL)에 실제로 어떤 칸들이 있는지 확인합니다.
    inspector = inspect(pg_engine)
    target_columns = [col['name'] for col in inspector.get_columns('news')]
    
    print(f"   - 클라우드 DB의 칸들: {target_columns}")

    # 💡 로컬 데이터에서 클라우드에 '있는' 칸들만 골라냅니다.
    common_columns = [col for col in news_df.columns if col in target_columns]
    news_df_filtered = news_df[common_columns]
    
    print(f"   - 전송할 칸들: {common_columns}")

    print("3. 데이터 복사 중... 🚀")
    # 필터링된 데이터만 전송
    news_df_filtered.to_sql('news', pg_engine, if_exists='append', index=False)

    print("✅ 완벽합니다! 클라우드 구조에 맞춰서 이사가 완료되었습니다!")

except Exception as e:
    print(f"❌ 에러 발생: {e}")

finally:
    sqlite_conn.close()