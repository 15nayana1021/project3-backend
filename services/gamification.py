from datetime import datetime
import aiosqlite
import os
from database import DB_PATH

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "DB_PATH")

# 레벨업 경험치 테이블
LEVEL_TABLE = {
    1: 100,
    2: 100,
    3: 200,
    4: 200,
    5: 300
}

# db 파라미터 추가
async def gain_exp(user_id: int, amount: int, max_level: int = None, db: aiosqlite.Connection = None):
    """
    유저에게 경험치를 지급하고, 레벨업을 체크합니다.
    db: 외부에서 이미 열린 DB 커넥션이 있다면 그걸 씁니다. (없으면 새로 만듦)
    """
    should_close_db = False
    
    try:
        # 1. 외부에서 DB 연결을 안 줬으면 -> 새로 만든다.
        if db is None:
            db = await aiosqlite.connect(DB_PATH)
            should_close_db = True

        # 2. 현재 정보 가져오기
        cursor = await db.execute("SELECT level, exp FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if not row:
            return 
        
        current_level, current_exp = row

        # 제한 레벨 확인
        if max_level is not None and current_level >= max_level:
            return

        # 3. 경험치 계산
        new_exp = current_exp + amount
        new_level = current_level
        
        # 4. 레벨업 체크
        while True:
            required_exp = LEVEL_TABLE.get(new_level, 999999) 
            if new_exp >= required_exp:
                new_exp -= required_exp
                new_level += 1
                print(f"🎉 [축하] 유저 {user_id}님이 레벨 {new_level}로 성장했습니다!")
            else:
                break
        
        # 5. DB 업데이트
        await db.execute("UPDATE users SET level = ?, exp = ? WHERE id = ?", (new_level, new_exp, user_id))
        
        # 외부에서 받은 DB면 commit을 밖에서 하겠지만, 안전을 위해 여기서도 저장
        if should_close_db:
            await db.commit()

        return {"level": new_level, "exp": new_exp, "leveled_up": new_level > current_level}

    except Exception as e:
        print(f"❌ gain_exp 에러: {e}")
    finally:
        if should_close_db and db:
            await db.close()

# 퀘스트 체크 함수도 마찬가지로 db 파라미터 추가
async def check_quest(user_id: int, quest_id: str, db: aiosqlite.Connection = None):
    """
    db 파라미터를 받아서 기존 트랜잭션에 참여합니다.
    """
    should_close_db = False
    try:
        if db is None:
            db = await aiosqlite.connect(DB_PATH)
            should_close_db = True

        # 이미 깼는지 확인
        cursor = await db.execute("SELECT is_completed FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, quest_id))
        row = await cursor.fetchone()
        if row and row[0]: return False 

        # 퀘스트 정보
        cursor = await db.execute("SELECT reward_exp FROM quests WHERE quest_id = ?", (quest_id,))
        quest_data = await cursor.fetchone()
        if not quest_data: return False

        reward = quest_data[0]
        
        # 완료 처리
        await db.execute("""
            INSERT OR REPLACE INTO user_quests (user_id, quest_id, is_completed, completed_at)
            VALUES (?, ?, 1, ?)
        """, (user_id, quest_id, datetime.now()))
        
        # 여기서도 db를 넘겨줌!
        await gain_exp(user_id, reward, db=db)
        
        if should_close_db:
            await db.commit()
            
        print(f"🏆 퀘스트 완료! [{quest_id}] 보상: {reward} EXP")
        return True
            
    except Exception as e:
        print(f"❌ check_quest 에러: {e}")
        return False
    finally:
        if should_close_db and db:
            await db.close()