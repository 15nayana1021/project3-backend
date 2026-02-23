import sqlite3

# 1. 내 DB 파일 열기 (이름이 stock_game.db 가 맞는지 확인!)
conn = sqlite3.connect("stock_game.db")
cursor = conn.cursor()

print("🛠️ 퀘스트 데이터 수리를 시작합니다...")

# 2. 매도 퀘스트가 없으면 넣기 (INSERT OR IGNORE: 이미 있으면 무시함)
queries = [
    # (1) 첫 매수 퀘스트
    """
    INSERT OR IGNORE INTO quests (quest_id, title, description, reward_exp)
    VALUES ('trade_first', '첫 주식 매수', '처음으로 주식을 매수해보세요.', 50);
    """,
    # (2) 첫 매도 퀘스트
    """
    INSERT OR IGNORE INTO quests (quest_id, title, description, reward_exp)
    VALUES ('trade_sell_first', '첫 수익 실현', '처음으로 주식을 판매해보세요.', 50);
    """
]

for q in queries:
    cursor.execute(q)

# 3. 테스트를 위해 '이미 깼다'는 기록 지우기 (초기화)
cursor.execute("DELETE FROM user_quests WHERE quest_id = 'trade_sell_first'")

# 4. 저장(Commit) 및 종료
conn.commit()
conn.close()

print("✅ 수리 완료! 이제 서버를 켜서 매도해보세요.")