# [scripts/clean_db.py]
import sqlite3
import os

def clean_null_news():
    # 1. 경로 설정 (이전과 동일)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(os.path.dirname(current_dir), "stock_game.db")
    if not os.path.exists(db_path):
        db_path = os.path.join(current_dir, "stock_game.db")

    print(f"📂 데이터베이스 위치: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🧹 [청소 시작] 불량 뉴스 데이터 박멸 중...")

        # 2. 삭제 전 개수 확인
        cursor.execute("SELECT COUNT(*) FROM news")
        before_count = cursor.fetchone()[0]

        # 🟢 [수정] 삭제 조건 강화!
        # 1. 진짜 SQL NULL인 경우
        # 2. 글자로 'NULL'이라고 적힌 경우
        # 3. 빈 따옴표('')인 경우
        # 4. 'None'이라고 적힌 경우
        query = """
            DELETE FROM news 
            WHERE content IS NULL 
               OR summary IS NULL 
               OR content = 'NULL' 
               OR summary = 'NULL'
               OR content = '' 
               OR summary = ''
               OR content = 'None'
               OR summary = 'None'
        """
        cursor.execute(query)
        deleted_rows = cursor.rowcount
        
        conn.commit()

        # 3. 마무리 정리 (VACUUM: DB 파일 용량 최적화)
        cursor.execute("VACUUM")

        # 4. 결과 확인
        cursor.execute("SELECT COUNT(*) FROM news")
        after_count = cursor.fetchone()[0]

        print(f"------------------------------------------------")
        print(f"🗑️  삭제된 뉴스 개수 : {deleted_rows}개")
        print(f"✨  남은 진짜 뉴스 개수: {after_count}개")
        print(f"------------------------------------------------")

        conn.close()

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    clean_null_news()