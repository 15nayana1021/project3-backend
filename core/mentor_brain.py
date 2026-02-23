import os
import json
import asyncio
from datetime import datetime
from openai import AsyncAzureOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import desc

# 기존에 만든 파일들 임포트
from database import DBAgent, DBCompany, DBNews, DBDiscussion, DBTrade
from core.mentor_personas import MentorType, MENTOR_PROFILES

# -----------------------------------------------------------------------------
# [설정] Azure OpenAI 클라이언트 세팅
# (실제 환경에 맞게 .env 파일이나 환경 변수로 설정하세요)
# -----------------------------------------------------------------------------
client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com/"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY", "your-api-key"),
    api_version="2024-02-15-preview"
)
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# -----------------------------------------------------------------------------
# 1. 시장 및 유저 관찰 (Observation & Memory - ASFM / AgentSociety 융합)
# -----------------------------------------------------------------------------
def gather_observation_data(db: Session, ticker: str, user_id: str = "USER_01"):
    """
    논문(ASFM, AgentSociety)의 Observation/Memory 모듈에 해당.
    현재 시장 상황과 유저의 과거 매매 기록을 긁어모읍니다.
    """
    company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
    user = db.query(DBAgent).filter(DBAgent.agent_id == user_id).first()
    
    if not company:
        return None

    # [ASFM] 1. 시장 팩트 (현재가, 최근 가격 변동)
    current_price = company.current_price
    recent_trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(10).all()
    price_trend = [t.price for t in recent_trades] if recent_trades else [current_price]

    # [ASFM] 2. 외부 환경 (최근 뉴스 3개)
    recent_news = db.query(DBNews).filter(DBNews.company_name == company.name).order_by(desc(DBNews.id)).limit(3).all()
    news_summaries = [f"- {n.title} ({n.summary})" for n in recent_news] if recent_news else ["- 최근 특별한 뉴스가 없습니다."]

    # [AgentSociety] 3. 사회적 환경 (종토방 여론)
    recent_posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == ticker).order_by(desc(DBDiscussion.created_at)).limit(5).all()
    community_vibe = [f"[{p.sentiment}] {p.content}" for p in recent_posts] if recent_posts else ["- 조용함"]

    # [AgentSociety] 4. 유저 개인의 기억 (Memory & State)
    user_portfolio_qty = 0
    user_avg_price = 0
    if user:
        user_portfolio_qty = user.portfolio.get(ticker, 0)
        user_avg_price = user.psychology.get(f"avg_price_{ticker}", 0)

    # 수익률 계산
    profit_rate = 0
    if user_avg_price > 0:
        profit_rate = round(((current_price - user_avg_price) / user_avg_price) * 100, 2)

    return {
        "company_name": company.name,
        "current_price": current_price,
        "price_trend": price_trend,
        "news": "\n".join(news_summaries),
        "community_vibe": "\n".join(community_vibe),
        "user_state": {
            "held_quantity": user_portfolio_qty,
            "avg_price": user_avg_price,
            "profit_rate": f"{profit_rate}%"
        }
    }

# -----------------------------------------------------------------------------
# 2. LLM 뇌 가동 (Cognition & Prompt Engineering)
# -----------------------------------------------------------------------------
async def ask_mentor(mentor_type: MentorType, obs_data: dict) -> dict:
    """
    특정 멘토 페르소나를 씌워 LLM에게 조언을 생성하도록 요청합니다.
    """
    persona = MENTOR_PROFILES[mentor_type]
    
    # 시스템 프롬프트: 페르소나 및 출력 형식 강제
    system_prompt = f"""
    당신은 주식 시장의 멘토 '{persona.name}' 입니다.
    당신의 성격과 말투: {persona.tone}
    당신의 분석 초점: {persona.focus_area}
    
    [핵심 지침]
    {persona.prompt_instruction}
    
    [출력 규칙]
    반드시 아래 JSON 형식으로만 답변하세요. 다른 말은 절대 덧붙이지 마세요.
    {{
        "opinion": "STRONG BUY, BUY, HOLD, SELL, STRONG SELL 중 택 1",
        "core_logic": "당신의 페르소나에 기반한 1~2줄의 핵심 분석 근거",
        "feedback_to_user": "유저의 현재 평단가와 수익률 상태를 보고 평가나 조언 (칭찬, 경고, 위로 등)",
        "chat_message": "유저에게 직접 건네는 대사 (당신의 말투를 완벽히 반영할 것)"
    }}
    """

    # 유저 프롬프트: ASFM + AgentSociety 기반 데이터
    user_prompt = f"""
    [현재 종목 상황]
    - 종목명: {obs_data['company_name']}
    - 현재가: {obs_data['current_price']}원
    - 최근 체결가 흐름: {obs_data['price_trend']}
    
    [최근 뉴스]
    {obs_data['news']}
    
    [커뮤니티(종토방) 여론]
    {obs_data['community_vibe']}
    
    [유저의 현재 상태 (Memory)]
    - 보유 수량: {obs_data['user_state']['held_quantity']}주
    - 평균 단가: {obs_data['user_state']['avg_price']}원
    - 현재 수익률: {obs_data['user_state']['profit_rate']}
    
    위 데이터를 바탕으로 {persona.name}의 관점에서 JSON으로 조언을 작성해주세요.
    유저가 손실 중이라면 당신의 성격에 맞게 위로하거나 꾸짖고, 수익 중이라면 칭찬하거나 익절을 권하세요.
    """

    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"} # JSON 모드 강제
        )
        
        result_text = response.choices[0].message.content
        return json.loads(result_text)
        
    except Exception as e:
        print(f"❌ 멘토 LLM 호출 실패 ({persona.name}): {e}")
        # 실패 시 Fallback(기본값) 반환
        return {
            "opinion": "HOLD",
            "core_logic": "일시적인 통신 장애로 분석이 어렵습니다.",
            "feedback_to_user": "현재 시장 데이터를 불러오는 중입니다. 잠시 후 다시 확인해주세요.",
            "chat_message": "잠시만요, 제 데이터 터미널에 오류가 생겼네요. 조금 뒤에 다시 뵙겠습니다."
        }

# -----------------------------------------------------------------------------
# 3. 통합 실행 함수 (Multi-Agent 동시 호출)
# -----------------------------------------------------------------------------
async def generate_all_mentors_advice(db: Session, ticker: str, user_id: str = "USER_01"):
    """
    모든 멘토(가이드, 가치, 공격, 비관)의 조언을 동시에 비동기로 생성합니다.
    """
    obs_data = gather_observation_data(db, ticker, user_id)
    if not obs_data:
        return {"error": "종목 데이터를 찾을 수 없습니다."}

    print(f"🧠 [{ticker}] 멘토 LLM 분석 시작... (비동기)")
    
    # 4명의 멘토에게 동시에 질문을 던집니다 (대기 시간 대폭 단축)
    tasks = [
        ask_mentor(MentorType.NEUTRAL, obs_data),
        ask_mentor(MentorType.VALUE, obs_data),
        ask_mentor(MentorType.MOMENTUM, obs_data),
        ask_mentor(MentorType.CONTRARIAN, obs_data)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # 결과를 예쁘게 딕셔너리로 매핑
    final_advice = {
        MentorType.NEUTRAL.value: results[0],
        MentorType.VALUE.value: results[1],
        MentorType.MOMENTUM.value: results[2],
        MentorType.CONTRARIAN.value: results[3],
        "generated_at": datetime.now().isoformat()
    }
    
    print(f"✅ [{ticker}] 멘토 분석 완료!")
    return final_advice

# -----------------------------------------------------------------------------
# [NEW] 챗봇용 자유 대화 함수 추가
# -----------------------------------------------------------------------------
async def chat_with_mentor(agent_type_str: str, user_message: str) -> str:
    """유저의 챗봇 자유 질문에 각 페르소나별로 응답합니다."""
    # 만약 에이전트 타입 매핑이 잘못되었을 경우 기본값 세팅
    try:
        mentor_type = MentorType[agent_type_str.upper()]
    except KeyError:
        mentor_type = MentorType.NEUTRAL

    persona = MENTOR_PROFILES[mentor_type]
    
    system_prompt = f"""
    당신은 주식 시장의 멘토 '{persona.name}' 입니다.
    당신의 성격과 말투: {persona.tone}
    당신의 분석 초점: {persona.focus_area}
    
    [핵심 지침]
    1. {persona.prompt_instruction}
    2. 사용자(개미 투자자)의 질문에 당신의 페르소나에 완벽하게 빙의하여 대답하세요.
    3. JSON이 아닌 자연스러운 일반 텍스트(문장) 형식으로 대답하세요.
    4. 너무 길지 않게 3~4문장 이내로 팩트와 감정을 섞어 짧고 굵게 말하세요.
    """

    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8
        )
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ 챗봇 LLM 호출 실패: {e}")
        return "죄송합니다. 현재 제 분석 터미널에 오류가 발생했습니다. 나중에 다시 질문해주세요."
# -----------------------------------------------------------------------------
# [테스트용 실행 코드]
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from database import SessionLocal
    
    async def test():
        db = SessionLocal()
        # 예시: AMD 주식과 같은 기술주인 IT008(소현컴퍼니)로 테스트
        advice = await generate_all_mentors_advice(db, "IT008", "USER_01")
        print(json.dumps(advice, indent=2, ensure_ascii=False))
        db.close()
        
    asyncio.run(test())