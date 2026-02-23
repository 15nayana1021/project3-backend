import sqlite3
import os

# DB 파일이 있는 경로 (현재 폴더의 stock_game.db)
db_path = "../stock_game.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🔨 랭킹 스냅샷 테이블 생성을 시작합니다...")

# 1. 기존 테이블이 있다면 삭제 (깨끗하게 다시 만들기 위해)
cursor.execute("DROP TABLE IF EXISTS ranking_snapshot")

# 2. 테이블 새로 만들기
cursor.execute("""
    CREATE TABLE ranking_snapshot (
        rank INTEGER,
        user_id INTEGER,
        username TEXT,
        total_asset REAL,
        profit_rate REAL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# 3. 테스트용 데이터 하나 넣기 (서버 켜자마자 잘 나오나 보려고)
cursor.execute("""
    INSERT INTO ranking_snapshot (rank, user_id, username, total_asset, profit_rate)
    VALUES (1, 999, '테스트유저', 1500000, 50.0)
""")

conn.commit()
conn.close()
print("✅ 테이블 생성 완료! 이제 에러가 사라질 겁니다.")