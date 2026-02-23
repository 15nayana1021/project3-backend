import sqlite3
import os

# 1. DB 파일 경로 찾기
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(os.path.dirname(current_dir), "stock-game.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # news 테이블에 category 컬럼 추가 (기본값: '일반')
    cursor.execute("ALTER TABLE news ADD COLUMN category TEXT DEFAULT '일반'")
    print("✅ 'category' 컬럼이 성공적으로 추가되었습니다!")
except Exception as e:
    print(f"ℹ️ 알림: {e} (이미 컬럼이 있거나 문제가 발생했습니다.)")

conn.commit()
conn.close()