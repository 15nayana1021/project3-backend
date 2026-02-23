import sqlite3
conn = sqlite3.connect("../stock_game.db")
cursor = conn.cursor()

# 4번 주문 강제 삭제
cursor.execute("DELETE FROM orders WHERE id = 4")
conn.commit()
conn.close()
print("✅ 4번 주문을 강제로 삭제했습니다. 이제 목록에서 안 보일 겁니다.")