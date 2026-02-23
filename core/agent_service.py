import os
import time
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from json_repair import repair_json

load_dotenv()

class StockAgentService:
    def __init__(self, mode="real"):
        self.endpoint = os.getenv("AZURE_AI_ENDPOINT")
        self.api_key = os.getenv("AZURE_AI_API_KEY") 
        self.mode = mode
        
        if mode == "virtual":
            self.agent_id = os.getenv("VIRTUAL_AGENT_ID")
            self.model_name = "gpt-4o-mini"
            print(f"🤖 가상 뉴스 생성 모드 (4o-mini) 활성화")
        else:
            self.agent_id = os.getenv("REAL_AGENT_ID")
            self.model_name = "gpt-4o"
            print(f"📡 실제 뉴스 분석 모드 (4o) 활성화")

        if not self.endpoint or not self.api_key:
            print("❌ 오류: .env 설정이 부족합니다.")
            self.client = None
            return

        try:
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-05-01-preview"
            )
            
            # 에이전트 유효성 검사 및 자동 생성
            self._ensure_agent_exists()
            
        except Exception as e:
            print(f"❌ 클라이언트 초기화 실패: {e}")
            self.client = None

    def _ensure_agent_exists(self):
        """에이전트 ID가 유효한지 확인하고, 없으면 새로 만듭니다."""
        if not self.client: return

        try:
            # 1. 기존 ID로 조회를 시도해봅니다.
            self.client.beta.assistants.retrieve(self.agent_id)
        except Exception:
            print(f"⚠️ 기존 에이전트({self.agent_id})를 찾을 수 없습니다.")
            print("✨ 새로운 에이전트를 자동으로 생성합니다...")
            
            try:
                # 2. 없으면 새로 만듭니다.
                instructions = "당신은 주식 뉴스 분석 및 생성 전문가입니다. 항상 JSON 형식으로 응답합니다."
                new_agent = self.client.beta.assistants.create(
                    name=f"StockAgent-{self.mode}",
                    instructions=instructions,
                    model=self.model_name 
                )
                # 3. 새로 만든 ID를 현재 실행 메모리에 적용합니다.
                self.agent_id = new_agent.id
                print(f"✅ 새 에이전트 생성 완료! ID: {self.agent_id}")
                print(f"📝 (참고) .env 파일의 {self.mode.upper()}_AGENT_ID를 이 값으로 바꿔주시면 재사용 가능합니다.")
            except Exception as e:
                print(f"❌ 에이전트 생성 실패: {e}")

    def _call_llm(self, prompt: str) -> str:
        if not self.client: return ""

        try:
            thread = self.client.beta.threads.create()
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt
            )

            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.agent_id
            )

            # 대기 루프
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

            if run.status == 'completed':
                messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                for msg in messages.data:
                    if msg.role == "assistant":
                        if msg.content:
                            return msg.content[0].text.value
            else:
                print(f"⚠️ 에이전트 응답 실패 상태: {run.status}")
                if hasattr(run, 'last_error') and run.last_error:
                    print(f"   -> 원인: {run.last_error}")
                return ""
            return ""

        except Exception as e:
            print(f"❌ Azure Agent 호출 중 오류 발생: {e}")
            return ""

    def analyze_stock_news(self, company_name: str, mode="real", count=2, company_desc: str = ""):
        desc_instruction = f"- 이 회사의 핵심 사업 모델은 '{company_desc}'입니다. 이와 관련된 전문 용어, 제품, 기술 동향을 반드시 기사에 포함하세요." if company_desc else ""

        if mode == "virtual":
            system_prompt = f"""
            당신은 냉철한 주식 전문 기자입니다. '{company_name}'에 대한 가상 뉴스를 반드시 {count}개 생성하되, 다음 규칙을 엄격히 지키세요.

            [규칙 0: 회사 맞춤형 뉴스 생성]
            {desc_instruction}
            - 단순한 뜬구름 잡는 소리가 아닌, 해당 산업군에서 실제로 일어날 법한 구체적인 이슈를 다루세요.

            [규칙 1: 현실적인 감성 분배]
            - 모든 뉴스가 긍정적일 수는 없습니다. 50%의 확률로 'negative' 뉴스를 생성하세요.
            - 악재 예시: 횡령, 실적 쇼크, 소송, 제품 결함, 규제 위반, 공급망 붕괴 등.

            [규칙 2: 점수(Impact Score)의 다양화]
            - 점수를 10점에서 95점 사이로 넓게 쓰세요.
            - 단순 협약이나 일상적인 기사는 30~50점.
            - 기업의 근간을 흔드는 초대형 호재/악재는 80~95점.
            - 어정쩡하게 80점만 주지 마세요.

            [규칙 3: 구체적인 본문]
            - 본문은 3문단 이상으로, 실제 기사처럼 수치와 정황을 가상으로 만들어 넣으세요.

            반드시 이 JSON 포맷으로만 응답하세요. 뉴스 {count}개가 배열 안에 들어가야 합니다:
            [
                {{
                    "title": "헤드라인1",
                    "content": "본문1",
                    "summary": "요약1",
                    "sentiment": "positive 또는 negative",
                    "impact_score": (내용에 맞는 10~95 사이의 숫자)
                }},
                {{
                    "title": "헤드라인2",
                    "content": "본문2",
                    "summary": "요약2",
                    "sentiment": "positive 또는 negative",
                    "impact_score": (내용에 맞는 10~95 사이의 숫자)
                }}
            ]
            """
        else: 
            system_prompt = f"'{company_name}' 뉴스 {count}개를 분석하여 위 JSON 포맷으로 응답하세요."

        #print(f"🤖 {company_name} 뉴스 생성 요청 중...")
        response_text = self._call_llm(system_prompt)

        if not response_text:
            return []

        try:
            news_data = repair_json(response_text, return_objects=True)
            if isinstance(news_data, dict):
                news_data = [news_data]
            return news_data
        except Exception:
            return []
        

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    agent_service = StockAgentService()
    # 이 API 키와 엔드포인트로 접근 가능한 모든 에이전트 가져오기
    assistants = agent_service.client.beta.assistants.list()
    
    print("\n" + "="*50)
    print("🔍 현재 연결된 리소스에서 발견된 모든 에이전트")
    print("="*50)
    
    if not assistants.data:
        print("❌ 발견된 에이전트가 하나도 없습니다. API 키나 엔드포인트를 확인하세요.")
    else:
        for asst in assistants.data:
            print(f"📌 이름: {asst.name}")
            print(f"🆔 ID: {asst.id}")
            print(f"📝 지침: {asst.instructions[:60]}...")
            print("-" * 50)