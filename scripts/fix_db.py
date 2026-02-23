# scripts/fix_db.py
import sqlite3
import os

# DB 파일 경로 (현재 위치 기준)
DB_PATH = "stock_game.db"

def fix_database_schema():
    print(f"🔧 DB 파일 확인 중: {os.path.abspath(DB_PATH)}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 추가해야 할 컬럼 목록
    new_columns = [
        ("ticker", "TEXT"),
        ("summary", "TEXT"),
        ("sentiment", "TEXT"),
        ("published_at", "TEXT")
    ]

    print("🚀 컬럼 추가 작업을 시작합니다...")

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE news ADD COLUMN {col_name} {col_type}")
            print(f"✅ [성공] '{col_name}' 컬럼이 추가되었습니다.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️ [패스] '{col_name}' 컬럼은 이미 존재합니다.")
            else:
                print(f"⚠️ [주의] '{col_name}' 추가 중 메시지: {e}")

    conn.commit()
    conn.close()
    print("\n✨ DB 스키마 복구가 완료되었습니다! 다시 뉴스를 생성해 보세요.")

if __name__ == "__main__":
    fix_database_schema()