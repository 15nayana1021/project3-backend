import sqlite3

# DB 파일 연결
conn = sqlite3.connect("../stock_game.db")
cursor = conn.cursor()

print("🔨 미체결 주문(orders) 테이블 생성을 시작합니다...")

# orders 테이블 생성 SQL 실행
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        company_name TEXT,
        order_type TEXT, 
        price REAL,
        quantity INTEGER,
        status TEXT DEFAULT 'PENDING', -- PENDING(대기), FILLED(체결), CANCELLED(취소)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
conn.close()
print("✅ orders 테이블 생성 완료! 이제 주문을 넣을 수 있습니다.")