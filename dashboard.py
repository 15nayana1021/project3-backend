import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from database import SessionLocal, DBTrade, DBCompany, DBAgent, DBNews
from sqlalchemy import desc
import os

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="Global Market Watch", layout="wide", page_icon="🌎")

st.markdown("""
    <style>
    .stMetric { background-color: #262730; padding: 15px; border-radius: 10px; border: 1px solid #444; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #1E1E1E; border-radius: 5px; }
    .stTabs [aria-selected="true"] { background-color: #4CAF50 !important; color: white !important; }
    /* 깜빡임 방지용 트릭: 메인 컨테이너 전환 효과 제거 */
    .element-container { transition: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 사이드바 (종목 & 뷰 설정)
# --------------------------------------------------------------------------
st.sidebar.title("🔍 Market Watch")

# DB 세션 연결
db = SessionLocal()

try:
    all_companies = db.query(DBCompany).all()
except Exception as e:
    st.error("DB 연결 중입니다... 잠시 후 다시 시도해주세요.")
    time.sleep(2)
    st.rerun()

if not all_companies:
    st.error("DB가 비어있습니다. 초기화가 필요합니다.")
    st.stop()

ticker_name_map = {c.ticker: c.name for c in all_companies}
ticker_list = list(ticker_name_map.keys())

# --- Session State로 선택값 유지 ---
if "saved_ticker" not in st.session_state:
    st.session_state["saved_ticker"] = "SS011" if "SS011" in ticker_list else ticker_list[0]

try:
    current_index = ticker_list.index(st.session_state["saved_ticker"])
except ValueError:
    current_index = 0

selected_ticker = st.sidebar.selectbox(
    "종목 선택", 
    ticker_list, 
    index=current_index, 
    format_func=lambda x: f"{ticker_name_map[x]} ({x})"
)
st.session_state["saved_ticker"] = selected_ticker
# ---------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔭 뷰 설정")
view_range = st.sidebar.slider("차트 데이터 개수 (Zoom)", min_value=30, max_value=500, value=50, step=10)

# --------------------------------------------------------------------------
# 3. 메인 화면 (st.fragment 적용 + Static Key 사용)
# --------------------------------------------------------------------------

@st.fragment(run_every=1)
def run_live_dashboard(ticker, view_count):
    # [수정] 매번 바뀌는 키(time.time)를 제거했습니다.
    
    with SessionLocal() as db:
        # DB 데이터 조회
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(view_count).all()
        company_news = db.query(DBNews).filter(DBNews.company_name == company.name).order_by(desc(DBNews.id)).limit(5).all()
        market_news = db.query(DBNews).order_by(desc(DBNews.id)).limit(10).all()
        
        # 자산 랭킹 계산
        agents = db.query(DBAgent).all()
        rich_list = []
        for ag in agents:
            if ag.agent_id == "MARKET_MAKER": continue 
            
            stock_val = 0
            if ag.portfolio:
                for tik, qty in ag.portfolio.items():
                    c_info = db.query(DBCompany).filter(DBCompany.ticker == tik).first()
                    if c_info:
                        stock_val += qty * c_info.current_price
            
            rich_list.append({
                "ID": ag.agent_id,
                "Total": int(ag.cash_balance + stock_val),
                "Cash": int(ag.cash_balance),
                "Stock": int(stock_val)
            })
        rich_list.sort(key=lambda x: x["Total"], reverse=True)

        # --- UI 그리기 ---
        st.title(f"🌏 {company.name} ({ticker})")
        
        col_chart, col_news = st.columns([2, 1])

        with col_chart:
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("현재가", f"{int(company.current_price):,}원")
            with m2: 
                last_trade_price = trades[1].price if len(trades) > 1 else company.current_price
                diff = company.current_price - last_trade_price
                st.metric("등락폭", f"{diff:+.0f}원", delta_color="normal")
            with m3:
                vol = sum([t.quantity for t in trades]) if trades else 0
                st.metric("구간 거래량", f"{vol:,}주")

            st.subheader(f"📈 실시간 시세 (최근 {view_count}건)")
            if trades:
                data = [{"time": t.timestamp, "price": t.price} for t in trades][::-1]
                df = pd.DataFrame(data)

                if not df.empty:
                    min_p = df['price'].min()
                    max_p = df['price'].max()
                    padding = (max_p - min_p) * 0.1 if max_p != min_p else max_p * 0.01
                    y_range = [min_p - padding, max_p + padding]
                    
                    start_p = df['price'].iloc[0]
                    last_p = df['price'].iloc[-1]
                    line_color = '#FF4040' if last_p >= start_p else '#00BFFF' 
                    fill_color = 'rgba(255, 64, 64, 0.1)' if last_p >= start_p else 'rgba(0, 191, 255, 0.1)'

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df['time'], y=df['price'], mode='lines+markers',
                        line=dict(color=line_color, width=2),
                        marker=dict(size=4),
                        fill='tozeroy', fillcolor=fill_color
                    ))

                    fig.update_layout(
                        height=400, template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, title=""),
                        yaxis=dict(
                            showgrid=True, gridcolor='rgba(128,128,128,0.2)', side='right',
                            tickformat=',', range=y_range
                        ),
                        margin=dict(l=10, r=10, t=20, b=20), showlegend=False
                    )
                    # [핵심] Key를 고정값("live_chart")으로 설정 -> 깜빡임 제거
                    st.plotly_chart(fig, key="live_chart", use_container_width=True)
            else:
                st.info("⏳ 거래 대기 중... (시뮬레이터를 실행해주세요)")

        with col_news:
            st.subheader("📰 뉴스 센터")
            tab1, tab2 = st.tabs(["📢 이 종목 뉴스", "⚡ 시장 전체 속보"])
            
            with tab1:
                if company_news:
                    for news in company_news:
                        emoji = "🔥" if news.impact_score > 0 else "💧" if news.impact_score < 0 else "📢"
                        st.info(f"{emoji} **{news.title}**\n\n{news.summary}")
                else:
                    st.markdown("🛑 *관련 뉴스가 없습니다.*")

            with tab2:
                if market_news:
                    for news in market_news:
                        st.markdown(f"> **[{news.company_name}]** {news.title}")
                else:
                    st.markdown("🛑 *뉴스가 없습니다.*")

        st.divider()
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("### 🧱 호가 매물대")
            if trades:
                df_vol = pd.DataFrame([{"price": t.price, "qty": t.quantity} for t in trades])
                price_dist = df_vol.groupby('price')['qty'].sum().reset_index().sort_values('qty').tail(10)
                
                fig_vol = go.Figure(go.Bar(
                    x=price_dist['qty'], y=price_dist['price'], orientation='h',
                    marker=dict(color='#FFD700'), text=price_dist['qty'], textposition='auto'
                ))
                fig_vol.update_layout(
                    height=300, template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(type='category', title='가격'), xaxis=dict(title='체결량'),
                    margin=dict(l=10, r=10, t=10, b=10)
                )
                # [핵심] Key를 고정값("vol_chart")으로 설정
                st.plotly_chart(fig_vol, key="vol_chart", use_container_width=True)

        with c2:
            st.markdown("### 🏆 부자 랭킹 (Top 7)")
            top_df = pd.DataFrame(rich_list[:7])
            st.dataframe(top_df.style.format({ "Total": "{:,}원", "Cash": "{:,}원", "Stock": "{:,}원" }), use_container_width=True, hide_index=True)

# 메인 실행
run_live_dashboard(selected_ticker, view_range)