import random
import uuid
from sqlalchemy.orm import Session
from database import SessionLocal, DBAgent, init_db
from models.domain_models import AgentState
import os

def create_agents():
    db: Session = SessionLocal()
    
    # 기존 에이전트 싹 지우기 (중복 방지)
    db.query(DBAgent).delete()
    db.commit()
    print("🧹 기존 에이전트 데이터 삭제 완료.")

    agents_data = []
    
    # ---------------------------------------------------------
    # 1. 고래 에이전트 (Whales) - 25명 (시장 주도 세력)
    # 특징: 돈이 엄청 많음 (1억 ~ 5억), 성향이 극단적임
    # ---------------------------------------------------------
    for i in range(25):
        agent_id = f"WHALE_{i+1:03d}" # 예: WHALE_001
        
        # 고래는 자본금이 1억 ~ 5억 원
        cash = random.randint(100_000_000, 500_000_000)
        
        # 고래 성향: 아주 공격적이거나(Greed), 아주 보수적이거나(Fear)
        if random.random() < 0.5:
            # 공격적 고래 (상승장 주도)
            state = AgentState(
                safety_needs=0.1, social_needs=0.2, 
                fear_index=0.1, greed_index=0.9, 
                current_context="나는 시장을 주도한다. 공격적 투자."
            )
        else:
            # 방어적 고래 (하락장 유도/현금보유)
            state = AgentState(
                safety_needs=0.9, social_needs=0.1, 
                fear_index=0.8, greed_index=0.1, 
                current_context="리스크 관리가 최우선. 보수적 운용."
            )

        agents_data.append(DBAgent(
            agent_id=agent_id,
            cash_balance=float(cash),
            portfolio={}, # 초기엔 주식 0주
            psychology=state.dict()
        ))

    # ---------------------------------------------------------
    # 2. 일반 에이전트 (Ants) - 475명 (개미 투자자)
    # 특징: 시드머니 200~500만 원, 일반적인 성향
    # ---------------------------------------------------------
    for i in range(475):
        agent_id = f"Citizen_{i+1:03d}" # 예: Citizen_001
        
        # 일반인은 자본금 200만 ~ 500만 원
        cash = random.randint(2_000_000, 5_000_000)
        
        # 성향은 랜덤 분포
        state = AgentState(
            safety_needs=random.random(), 
            social_needs=random.random(),
            fear_index=random.random(), 
            greed_index=random.random(),
            current_context="소액으로 꾸준한 수익을 목표로 함."
        )

        agents_data.append(DBAgent(
            agent_id=agent_id,
            cash_balance=float(cash),
            portfolio={},
            psychology=state.dict()
        ))

    # DB에 일괄 저장
    db.bulk_save_objects(agents_data)
    db.commit()
    
    # [수정됨] 텍스트를 실제 숫자에 맞게 변경
    print(f"✅ 총 {len(agents_data)}명 (고래 25명 + 일반 475명) 생성 완료!")
    db.close()

if __name__ == "__main__":
    # 테이블이 없으면 생성
    init_db()
    create_agents()