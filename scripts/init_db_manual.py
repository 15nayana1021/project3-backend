import sqlite3
import os

# DB 파일 경로 설정
db_path = "../stock_game.db" 

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"🔨 '{db_path}' 파일에 테이블 생성을 시작합니다...")

# 1. users 테이블
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        current_balance REAL DEFAULT 1000000
    )
""")
print("- Users 테이블 확인 완료")

# 2. holdings 테이블
cursor.execute("""
    CREATE TABLE IF NOT EXISTS holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        company_name TEXT,
        quantity INTEGER DEFAULT 0,
        average_price REAL DEFAULT 0,
        UNIQUE(user_id, company_name)
    )
""")
print("- Holdings 테이블 확인 완료")

# 3. transactions 테이블
cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        transaction_type TEXT,
        amount REAL,
        balance_after REAL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("- Transactions 테이블 확인 완료")


# 4. news 테이블
cursor.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        title TEXT,
        content TEXT,
        summary TEXT,
        sentiment TEXT,
        impact_score INTEGER,
        category TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
print("- ✅ News 테이블 생성 완료!")

conn.commit()
conn.close()
print("🎉 모든 테이블 생성 완료! 이제 뉴스 생성을 다시 시도해보세요.")