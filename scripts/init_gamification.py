import sqlite3
import os

# DB 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "stock_game.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("🔨 게이미피케이션 DB 업데이트 시작...")

# 1. Users 테이블에 level, exp 컬럼 추가 (없을 경우에만)
try:
    cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
    cursor.execute("ALTER TABLE users ADD COLUMN exp INTEGER DEFAULT 0")
    print("✅ Users 테이블에 level, exp 컬럼 추가 완료.")
except sqlite3.OperationalError:
    print("ℹ️ 이미 level, exp 컬럼이 존재합니다.")

# 2. 퀘스트 목록 (Quest Definitions) - 하드코딩 대신 DB로 관리하면 확장이 편함
cursor.execute("""
    CREATE TABLE IF NOT EXISTS quests (
        quest_id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        target_value INTEGER,
        reward_exp INTEGER
    )
""")

# 초기 퀘스트 데이터 넣기
initial_quests = [
    ("news_read_1", "정보 수집가", "뉴스 1개 읽기", 1, 10),
    ("trade_first", "첫 투자", "주식 1주 매수하기", 1, 50),
    ("level_5", "개미 탈출", "레벨 5 달성하기", 5, 100)
]
cursor.executemany("INSERT OR IGNORE INTO quests VALUES (?, ?, ?, ?, ?)", initial_quests)

# 3. 유저 퀘스트 달성 기록 (User Quest Progress)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_quests (
        user_id INTEGER,
        quest_id TEXT,
        is_completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP,
        PRIMARY KEY (user_id, quest_id)
    )
""")

conn.commit()
conn.close()
print("🎉 게이미피케이션 DB 준비 완료!")