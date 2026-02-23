import sqlite3
import os

def get_db_path():
    """
    현재 파일 위치를 기준으로 'easystock-backend' 폴더 안의 DB 경로를 정확히 찾습니다.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(current_dir)
    return os.path.join(backend_root, "stock-game.db")

def save_news_to_db(ticker: str, news_list: list, category: str = "일반"):
    """
    뉴스 데이터를 DB에 저장합니다. (영향력 점수 보정, 카테고리, 출처 포함)
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        try:
            cursor.execute("ALTER TABLE news ADD COLUMN ticker TEXT")
        except:
            pass

        saved_count = 0
        for news in news_list:
            # 1. 데이터 추출
            title = news.get("title", "제목 없음")
            content = news.get("content", news.get("summary", "내용 없음"))
            summary = news.get("summary", "") 
            sentiment = news.get("sentiment", "neutral")
            
            # 출처(Source) 지정
            source = news.get("source", "Stocky AI")
            
            # 영향력 점수(Impact Score) 보정 로직
            impact = news.get("impact_score", news.get("impact", 50))

            # 악재(negative)면 점수를 마이너스로, 호재(positive)면 플러스로 변환
            if sentiment == "negative" and impact > 0:
                impact = -impact
            elif sentiment == "positive" and impact < 0:
                impact = abs(impact)
            
            # 3. DB 저장 (source, category, ticker 모두 포함)
            cursor.execute("""
                INSERT INTO news (
                    ticker, 
                    title, 
                    content, 
                    summary, 
                    sentiment, 
                    impact_score,
                    source,
                    category,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (ticker, title, content, summary, sentiment, impact, source, category))
            
            saved_count += 1
            
        conn.commit()
        print(f"💾 [{ticker}] 뉴스 {saved_count}건 저장 완료 (카테고리: {category})")
        
    except Exception as e:
        print(f"❌ 뉴스 저장 실패 ({ticker}): {e}")
    finally:
        conn.close()