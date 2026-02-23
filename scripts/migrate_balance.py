import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "stock_game.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print(f"🚚 자산 데이터 이사를 시작합니다... (current_balance -> balance)")

try:
    # 1. current_balance(옛날 돈)가 있는 경우, 그 값을 balance(새 돈)로 덮어씌움
    cursor.execute("""
        UPDATE users 
        SET balance = current_balance 
        WHERE current_balance IS NOT NULL
    """)
    
    # 2. 변경사항 저장
    conn.commit()
    print("✅ 이사 완료! 이제 'current_balance'의 금액이 'balance'로 옮겨졌습니다.")

    # 3. 확인용 출력
    cursor.execute("SELECT id, username, current_balance, balance FROM users LIMIT 3")
    rows = cursor.fetchall()
    print("\n[결과 확인]")
    for row in rows:
        print(f"유저 {row[0]}: 옛날지갑({row[2]}) => 새지갑({row[3]})")

except Exception as e:
    print(f"❌ 오류 발생: {e}")

conn.close()