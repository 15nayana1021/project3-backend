import sqlite3
import os

# 현재 폴더에 있는 stock_game.db를 봅니다
db_path = "stock_game.db"

if not os.path.exists(db_path):
    print(f"❌ 오류: {db_path} 파일 자체가 없습니다!")
else:
    print(f"✅ 확인: {db_path} 파일을 찾았습니다.")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 뉴스 데이터 확인
    try:
        cursor.execute("SELECT count(*) FROM news_pool")
        count = cursor.fetchone()[0]
        print(f"📰 뉴스 개수: {count}개", end="")
        if count == 0:
            print(" (🚨 비어있음! 뉴스가 안 뜰 수밖에 없음)")
        else:
            print(" (정상)")
    except sqlite3.OperationalError:
        print("❌ 뉴스 테이블(news_pool)이 아예 없습니다.")

    # 2. 주식 데이터 확인
    try:
        cursor.execute("SELECT count(*) FROM stocks")
        count = cursor.fetchone()[0]
        print(f"📈 주식 종목: {count}개", end="")
        if count == 0:
            print(" (🚨 비어있음! 호가창이 안 뜸)")
        else:
            print(" (정상)")
    except:
        print("❌ 주식 테이블(stocks)이 없습니다.")

    # 3. 유저 확인
    try:
        cursor.execute("SELECT count(*) FROM users")
        print(f"👤 유저 수: {cursor.fetchone()[0]}명")
    except:
        print("❌ 유저 테이블(users)이 없습니다.")

    conn.close()