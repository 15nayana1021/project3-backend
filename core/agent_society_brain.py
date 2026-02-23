import os
import json
import random
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
from models.domain_models import AgentState

load_dotenv()

client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
AGENT_MODEL = os.getenv("MODEL_AGENT", "gpt-4o-mini") 

# [ASFM 논문 Appendix A.1 기반] 페르소나 정의
def get_agent_persona(agent_name):
    try:
        parts = agent_name.split('_')
        idx = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else random.randint(0, 99)
    except:
        idx = random.randint(0, 99)

    mod = idx % 10
    if mod < 4: 
        return "Value Investor (가치 투자자)", \
               "기업의 펀더멘탈과 내재 가치를 믿습니다. 저평가 시 매수하고, 단기 등락에 흔들리지 않는 뚝심이 있습니다."
    elif mod < 6: 
        return "Institutional Investor (기관 투자자)", \
               "철저한 리스크 관리와 포트폴리오 안정을 추구합니다. 불확실성을 싫어하며, 근거 없는 급등에는 참여하지 않습니다."
    elif mod < 8: 
        return "Contrarian Investor (역발상 투자자)", \
               "대중과 반대로 행동합니다. 남들이 환호할 때 팔고, 공포에 질려 던질 때 줍습니다. 군중 심리를 역이용합니다."
    else: 
        return "Aggressive Speculator (공격적 투기꾼)", \
               "모멘텀과 추세를 추종합니다. 오르는 말에 올라타는 것을 즐기며, 하이 리스크 하이 리턴을 추구합니다."

# [AgentSociety 논문 핵심] 흐름(Stream)과 상호작용(Interaction)이 추가된 뇌
async def agent_society_think(
    agent_name, 
    agent_state: AgentState, 
    context_info, 
    current_price, 
    cash, 
    portfolio_qty=0, 
    avg_price=0,
    last_action_desc=None, 
    market_sentiment=None  
):
    agent_type, strategy_prompt = get_agent_persona(agent_name)

    # 🔥 현재 상황이 '매매'인지 '커뮤니티 수다'인지 판정
    is_social_mode = (current_price <= 0)

    # 1. 자산 상태 분석
    status_msg = "보유 주식 없음"
    if portfolio_qty > 0 and avg_price > 0 and not is_social_mode:
        roi = ((current_price - avg_price) / avg_price) * 100
        roi_str = f"{roi:+.2f}%"
        if roi > 0: status_msg = f"🟢 수익 중 ({roi_str})"
        else: status_msg = f"🔴 손실 중 ({roi_str})"
    elif is_social_mode:
        status_msg = "전체 계좌 상황을 보며 커뮤니티 활동 중"

    # 2. [Stream Memory] 기억 복원
    memory_context = "최근 거래 기록 없음."
    if last_action_desc:
        memory_context = f"📜 [직전 기억]: 당신은 지난번에 '{last_action_desc}'라고 생각하고 행동했습니다."

    # 3. [Social Interaction] 사회적 분위기
    social_context = "시장 분위기 파악 불가."
    if market_sentiment:
        social_context = f"👥 [시장 분위기]: {market_sentiment}"

    # 4. 시스템 프롬프트 구성
    mode_instruction = "당신은 현재 주식 커뮤니티 라운지에서 사람들과 자유롭게 소통 중입니다. 매매가 목적이 아니므로 자연스러운 잡담을 하세요." if is_social_mode else "당신은 현재 특정 종목을 매매할지 결정해야 합니다."
    
    system_prompt = f"""
    당신은 '{agent_name}' ({agent_type})입니다. {mode_instruction}
    
    [당신의 투자 철학]
    {strategy_prompt}
    
    [행동 원칙]
    1. **사회적 상호작용:** 시장 사람들의 반응에 대해 당신의 성격대로 한마디 던지세요. 
    2. **감정 표현:** 기계적인 분석이 아니라, 사람처럼 기뻐하거나 한탄하거나 훈수를 두세요.
    3. **JSON 형식:** 반드시 아래 지정된 JSON 형식으로만 응답해야 합니다.
    """
    
    # 5. 유저 프롬프트 구성
    market_data_display = f"현재 {context_info}에 대해 토론 중" if is_social_mode else f"종목 현재가: {int(current_price):,}원"
    
    user_prompt = f"""
    [{'커뮤니티 라운지' if is_social_mode else '시장 데이터'}]
    - 상황: {market_data_display}
    - {social_context}
    
    [당신의 상태]
    - 현금: {int(cash):,}원
    - 주식 보유 현황: {portfolio_qty}주 (평단 {int(avg_price):,}원)
    - 현재 심리: {status_msg}
    - {memory_context}
    
    위 상황에서 당신의 성격이 드러나는 자연스러운 커뮤니티 글(thought_process)을 작성하고 의사결정을 내리세요.
    수다 모드일 때는 action은 'HOLD', price와 quantity는 0으로 하세요.

    {{
        "thought_process": "당신의 페르소나가 드러나는 자연스러운 커뮤니티 게시글 내용 (딱 한 문장)",
        "action": "BUY" 또는 "SELL" 또는 "HOLD",
        "price": (희망 가격, 정수),
        "quantity": (수량, 정수)
    }}
    """

    try:
        response = await client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9, 
            response_format={"type": "json_object"},
            max_tokens=300
        )
        
        raw_content = response.choices[0].message.content
        
        # 🟢 1단계 방어막: 뇌정지 방지
        if raw_content is None:
            print(f"⚠️ [{agent_name}] LLM 응답 없음. 기본값 처리.")
            decision = {
                "thought_process": "시장이 조용하군요. 상황을 지켜보겠습니다.", 
                "action": "HOLD", "quantity": 0, "price": int(current_price)
            }
        else:
            decision = json.loads(raw_content.strip())
            
        # 🟢 2단계 방어막: JSON은 왔는데 'thought_process'가 없을 때 터지는 현상 방지
        if "thought_process" not in decision:
            decision["thought_process"] = "현재 관망 중입니다."

    except Exception as e:
        error_msg = str(e)
        if "content_filter" in error_msg or "ResponsibleAIPolicyViolation" in error_msg:
            print(f"⚠️ [{agent_name} 검열 경고] 표현이 필터링 되었습니다. 기본 멘트 출력.")
            decision = {
                "thought_process": "흥미로운 장세네요. 신중하게 접근해야겠습니다.",
                "action": "HOLD", "quantity": 0, "price": int(current_price)
            }
        else:
            print(f"❌ [{agent_name}] 뇌정지 에러: {e}")
            decision = {
                "thought_process": "생각 중입니다...",
                "action": "HOLD", "quantity": 0, "price": int(current_price)
            }

    # --- 🔥 정상 로직(매매 계산 등)은 try-except 밖에서 무조건 실행됩니다! ---
    try:
        action = str(decision.get("action", "HOLD")).upper()
        
        # 수다 모드(is_social_mode)일 때는 복잡한 매매 검증을 스킵하고 바로 반환
        if is_social_mode:
            decision["action"] = "HOLD"
            decision["price"] = 0
            decision["quantity"] = 0
            return decision

        # 1. 안전한 수량 파싱
        try:
            qty = int(float(decision.get("quantity", 0)))
        except: qty = 0

        # 2. 안전한 가격 파싱
        try:
            raw_p = decision.get("price", current_price)
            raw_price = int(float(raw_p)) if raw_p not in [None, "", "null"] else int(current_price)
        except: raw_price = int(current_price)

        # 3. 가격 캡 씌우기
        if raw_price <= 0: raw_price = int(current_price)
        price = max(int(current_price * 0.85), min(raw_price, int(current_price * 1.15)))
        
        decision["price"] = price
        decision["quantity"] = qty

        # 4. 매수/매도 제한 로직
        if action == "BUY":
            if price > 0:
                max_buyable = int(cash // price)
                decision["quantity"] = min(qty, max_buyable)
            else:
                return {"action": "HOLD", "quantity": 0, "price": 0, "thought_process": decision.get("thought_process", "관망")}
        
        elif action == "SELL":
            if portfolio_qty == 0:
                return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": "보유 주식 없음"}
            decision["quantity"] = min(qty, portfolio_qty)

        if action != "HOLD" and decision["quantity"] <= 0:
             return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": "수량 부족으로 관망"}

        return decision

    except Exception as e:
        print(f"❌ [{agent_name}] 로직 처리 중 최후 에러: {e}")
        return {"action": "HOLD", "quantity": 0, "price": int(current_price), "thought_process": "에러 복구 관망"}