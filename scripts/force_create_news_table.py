import sqlite3
import os

# 현재 스크립트의 위치 (easystock-backend/scripts)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 프로젝트 루트 폴더 (easystock-backend)
project_root = os.path.dirname(current_dir)

# 가능성 있는 모든 DB 파일 이름 후보
db_candidates = [
    "easystock.db",
    "stock_game.db",
    "database.db",
    "instance/easystock.db"
]

print(f"📂 프로젝트 루트: {project_root}")
print("============== 작업 시작 ==============")

success_count = 0

for db_name in db_candidates:
    db_path = os.path.join(project_root, db_name)
    
    # DB 파일이 존재하는지 확인 (없으면 새로 만듦)
    print(f"🔍 확인 중: {db_path}")
    
    try:
        # 폴더가 없으면 에러나니까 체크 (instance 폴더 등)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # News 테이블 생성 쿼리 (강제 실행)
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
        
        conn.commit()
        conn.close()
        print(f"   ✅ 성공! '{db_name}' 파일에 news 테이블을 생성했습니다.")
        success_count += 1
        
    except Exception as e:
        print(f"   ⚠️ 실패 ({db_name}): {e}")

print("=======================================")
if success_count > 0:
    print(f"🎉 총 {success_count}개의 DB 파일에 테이블 생성을 완료했습니다.")
    print("이제 뉴스 생성을 다시 시도해보세요!")
else:
    print("❌ 테이블 생성에 실패했습니다. 관리자 권한 등을 확인해주세요.")