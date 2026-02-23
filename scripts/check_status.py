import sqlite3

conn = sqlite3.connect("../stock_game.db")
cursor = conn.cursor()

# 문제의 3번 주문 상태 확인
cursor.execute("SELECT id, status FROM orders WHERE id = 3")
row = cursor.fetchone()

if row:
    print(f"🕵️‍♂️ 3번 주문의 현재 상태: [{row[1]}]")
    if row[1] == 'FILLED':
        print("👉 결론: 이미 체결된 주문입니다. (취소 불가능이 정상)")
    elif row[1] == 'CANCELLED':
        print("👉 결론: 이미 취소된 주문입니다.")
    else:
        print("👉 결론: 아직 대기(PENDING) 상태입니다.")
else:
    print("❌ 주문이 존재하지 않습니다.")

conn.close()