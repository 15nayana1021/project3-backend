import os
import sys
import sqlite3
import time
import requests
import xml.etree.ElementTree as ET 
import random

# 1. 경로 설정
current_file = os.path.abspath(__file__)
scripts_folder = os.path.dirname(current_file)
backend_root = os.path.dirname(scripts_folder)
if backend_root not in sys.path: sys.path.insert(0, backend_root)
os.chdir(backend_root)

try:
    from core.agent_service import StockAgentService
    from database import DB_NAME 
except ImportError:
    DB_PATH = "/home/site/wwwroot/stock_game.db" if os.getenv("WEBSITE_HOSTNAME") else "stock_game.db"
    from core.agent_service import StockAgentService

# 기업 매핑 규칙
REAL_NEWS_TARGETS = [
    {
        "real_name": "삼성전자", 
        "game_name": "삼송전자", 
        "category": "전자",
        "replacements": {"삼성전자": "삼송전자", "삼성": "삼송", "Samsung": "Samsong", "갤럭시": "갤락수"}
    },
    {
        "real_name": "Microsoft", 
        "game_name": "마이크로하드", 
        "category": "IT",
        "replacements": {"Microsoft": "Microhard", "마이크로소프트": "마이크로하드", "Windows": "Doors"}
    }
]

def fetch_real_news_headlines(query, count=10):
    """Google News RSS에서 제목과 실제 언론사 이름을 추출합니다."""
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall('.//item')[:count]:
            title = item.find('title').text
            source_element = item.find('source')
            source_name = source_element.text if source_element is not None else "경제신문"
            articles.append({"title": title, "source": source_name})
        return articles
    except: return []

def run_real_news_batch():
    agent = StockAgentService()
    db_path = os.path.join(backend_root, DB_NAME)
    print(f"\n🌍 [Real-World Connect] 실제 언론사 정보를 포함하여 수집을 시작합니다.")

    for target in REAL_NEWS_TARGETS:
        real_name = target['real_name']
        game_name = target['game_name']
        
        real_articles = fetch_real_news_headlines(real_name, count=10)
        if not real_articles: continue

        for article in real_articles:
            print(f" ✍️ [{article['source']}] 실제 기사 변환 중...", end="", flush=True)
            
            prompt = f"""
            아래 실제 기사(출처: {article['source']})를 바탕으로 '{game_name}'의 패러디 기사를 만드세요.
            실제 제목: {article['title']}
            변환 규칙: {target['replacements']}

            반드시 아래 JSON 리스트 포맷으로 응답하세요:
            [
                {{
                    "title": "변환된 제목",
                    "content": "패러디된 본문 (3문단)",
                    "summary": "한 줄 요약",
                    "sentiment": "positive/negative",
                    "impact_score": 10~95 사이 숫자
                }}
            ]
            """
            analysis = agent.analyze_stock_news(prompt, mode="direct") 
            
            if analysis:
                # 리스트라면 첫 번째 항목만 꺼내서 딕셔너리로 만듭니다.
                if isinstance(analysis, list) and len(analysis) > 0:
                    final_news = analysis[0]
                else:
                    final_news = analysis
                
                # 실제 RSS에서 가져온 언론사 이름을 AI 응답 데이터에 합칩니다.
                if isinstance(final_news, dict):
                    final_news['source'] = article['source']
                    # 저장 함수 호출
                    save_to_db(db_path, game_name, target['category'], real_name, final_news)
                    print(f" -> ✅ 저장 완료 ({article['source']})")
                else:
                    print(" -> ❌ 데이터 변환 실패")
            
            time.sleep(1)

def save_to_db(db_path, game_name, category, real_name, news):
    """DB에 뉴스를 저장합니다 (source 컬럼 포함)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # source 컬럼이 있는지 확인하고 없으면 추가 (자동 수리)
        cursor.execute("PRAGMA table_info(news)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'source' not in cols:
            cursor.execute("ALTER TABLE news ADD COLUMN source TEXT")

        # 점수 보정 (Negative는 음수로)
        score = abs(news.get('impact_score', 0))
        if 'negative' in str(news.get('sentiment', '')).lower(): 
            score = -score

        cursor.execute("""
            INSERT INTO news (
                company_name, category, title, content, summary, 
                sentiment, impact_score, ticker, source, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            game_name,
            category,
            news.get('title'),
            news.get('content'),
            news.get('summary'),
            news.get('sentiment'),
            score,
            real_name,
            news.get('source')
        ))
        conn.commit()
    except Exception as e:
        print(f" -> ❌ DB 저장 중 에러: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_real_news_batch()