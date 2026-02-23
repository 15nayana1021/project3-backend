import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# 유지할 에이전트 ID
KEEP_IDS = [
    "asst_yUNoPGWFi87yBeFnWpEi8Cit",  # REAL_AGENT_ID
    "asst_oMbzIw3pLnbp6iziBfHDZFn0"   # VIRTUAL_AGENT_ID
]

def cleanup_assistants():
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_AI_API_KEY"),
        api_version="2024-05-01-preview",
        azure_endpoint=os.getenv("AZURE_AI_ENDPOINT")
    )

    print(f"📡 연결 중: {client.base_url}")
    print("🔍 에이전트 목록 불러오는 중...")
    
    try:
        response = client.beta.assistants.list(limit=100)
        all_assistants = response.data
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return

    if not all_assistants:
        print("❓ 발견된 에이전트가 없습니다. API 키와 엔드포인트를 다시 확인하세요.")
        return

    print(f"✅ 총 {len(all_assistants)}개의 에이전트를 발견했습니다.\n")
    deleted_count = 0

    for assistant in all_assistants:
        if assistant.id in KEEP_IDS:
            print(f"🛡️ [보호] 유지함: {assistant.name} ({assistant.id})")
        else:
            print(f"🗑️ [삭제] 중...: {assistant.name} ({assistant.id})")
            try:
                client.beta.assistants.delete(assistant.id)
                deleted_count += 1
            except Exception as e:
                print(f"   ⚠️ 삭제 실패: {e}")

    print("\n" + "="*40)
    print(f"✨ 정리 끝! {deleted_count}개를 삭제했습니다.")
    print("="*40)

if __name__ == "__main__":
    cleanup_assistants()