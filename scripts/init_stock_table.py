import sqlite3

conn = sqlite3.connect("../stock_game.db")
cursor = conn.cursor()

# stocks 테이블 생성 (종목명, 현재가)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        company_name TEXT PRIMARY KEY,
        current_price REAL DEFAULT 0
    )
""")

# 초기 데이터 넣기 (기본값)
initial_stocks = [
    ("삼송전자", 80000),
    ("테슬라", 250000),
    ("엔비디아", 1200000),
    ("비트코인", 100000000)
]

for name, price in initial_stocks:
    cursor.execute("INSERT OR IGNORE INTO stocks (company_name, current_price) VALUES (?, ?)", (name, price))

conn.commit()
conn.close()
print("✅ 주가 저장소(stocks 테이블)가 생성되었습니다.")