import streamlit as st
import matplotlib.pyplot as plt
import os
import yfinance as yf

# 커스텀 모듈 임포트 (확실하게 연결됨)
from data_loader import get_macro_data, get_unified_data, find_ticker
from logic import analyze_cli_trend
from ai_analyst import ask_ai

# 페이지 설정
st.set_page_config(page_title="Global EPS Trader", page_icon="📈", layout="wide")

if os.name == 'posix': plt.rcParams['font.family'] = 'AppleGothic'
else: plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
plt.style.use('ggplot')

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2910/2910312.png", width=50)
    st.header("Global EPS Trader")
    st.info("AI 기반 퀀트 분석 포트폴리오")
    user_input = st.text_input("종목명 또는 티커", "삼성전자")
    run = st.button("🚀 분석 실행", type="primary")
    st.markdown("---")
    with st.expander("📊 로직 가이드"):
        st.markdown("""
        **1. 12M Fwd EPS**: Rolling Sum 방식
        **2. 가속도(2차 미분)**: 성장 속도의 변화
        **3. 매크로**: CLI 국면 + 금리 위험 분석
        """)

st.title("📈 AI Quantitative Analyst Portfolio")
st.markdown("##### :gray[Macro-Driven & Earnings Acceleration Strategy]")

# 1. Macro Dashboard (수정된 부분)
y_c, h_s, cli = get_macro_data()
y_val, h_val = 0, 0
bond_risk_msg = "안정"

if not y_c.empty: y_val = y_c.iloc[-1,0]
if not h_s.empty: h_val = h_s.iloc[-1,0]

# 채권 위험 로직
if y_val < 0 and h_val >= 6.0: bond_risk_msg = "🚨 [심각] 금융 위기 (강력 매도)"
elif y_val < 0: bond_risk_msg = "⚠️ [주의] 경기 침체 시그널"

# CLI 지수 분석 변수 초기화
u_msg, u_col, u_val_str = "로딩 중", "gray", "-"
k_msg, k_col, k_val_str = "로딩 중", "gray", "-"

if not cli.empty:
    # 미국 분석
    if '미국_CLI' in cli.columns:
        u = cli['미국_CLI'].dropna()
        if len(u) >= 3:
            u_msg, u_col = analyze_cli_trend(u.iloc[-1], u.iloc[-2], u.iloc[-3])
            u_val_str = f"{u.iloc[-1]:.2f}"
    
    # 한국 분석 (이 부분이 누락되었었습니다!)
    if '한국_CLI' in cli.columns:
        k = cli['한국_CLI'].dropna()
        if len(k) >= 3:
            k_msg, k_col = analyze_cli_trend(k.iloc[-1], k.iloc[-2], k.iloc[-3])
            k_val_str = f"{k.iloc[-1]:.2f}"

# UI 출력 (4개의 컬럼으로 확장)
m1, m2, m3, m4 = st.columns(4)
m1.metric("장단기 금리차", f"{y_val:.2f}%p", delta="위험" if y_val<0 else "정상", delta_color="inverse")
m2.metric("하이일드 스프레드", f"{h_val:.2f}%", delta="위험" if h_val>=6 else "안정", delta_color="inverse")
m3.metric("🇺🇸 미국 CLI", u_val_str)
m4.metric("🇰🇷 한국 CLI", k_val_str)

st.caption(f"📊 매크로 진단: **미국 :{u_col}[{u_msg}]** / **한국 :{k_col}[{k_msg}]** / **채권 시장 {bond_risk_msg}**")

# 2. Analysis Execution
if run:
    st.divider()
    with st.spinner(f"🔍 '{user_input}' 정밀 분석 중..."):
        ticker, name, country = find_ticker(user_input)
        df_ui, trend_df = get_unified_data(ticker, country)
        
        curr_p = 0
        try: curr_p = yf.Ticker(ticker).history(period='1d')['Close'].iloc[-1]
        except: pass
        p_fmt = f"${curr_p:,.2f}" if country=="US" else f"{curr_p:,.0f}원"
        
        fwd_val, growth_val, accel_val = 0, 0, 0
        trade_signal = "데이터 부족"
        signal_color = "gray"
        
        if not trend_df.empty and len(trend_df) >= 3:
            fwd_val = trend_df.iloc[-1, 0]
            eps_prev = trend_df.iloc[-2, 0]
            eps_pprev = trend_df.iloc[-3, 0]
            
            # [핵심] 1차 미분(속도) 및 2차 미분(가속도) 계산
            growth_now = ((fwd_val - eps_prev) / abs(eps_prev)) * 100 if eps_prev != 0 else 0
            growth_prev = ((eps_prev - eps_pprev) / abs(eps_pprev)) * 100 if eps_pprev != 0 else 0
            
            growth_val = growth_now
            accel_val = growth_now - growth_prev
            
            # 신호 판정 로직
            if fwd_val > eps_prev:
                if accel_val > 0:
                    trade_signal = "🚀 적극 매수 (성장 가속)"
                    signal_color = "green"
                else:
                    trade_signal = "⚠️ 소극 대응 (탄력 둔화)"
                    signal_color = "orange"
            else:
                trade_signal = "🚨 매도/관망 (역성장)"
                signal_color = "red"
        
        # AI Opinion
        ai_res = ask_ai(ticker, name, fwd_val, growth_val, f"{accel_val:+.2f}%p", bond_risk_msg, u_msg, trade_signal)
        
        # Result Display
        st.subheader(f"{name} ({ticker}) 분석 결과")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재 주가", p_fmt)
        c2.metric("12M Fwd EPS", f"{fwd_val:,.2f}")
        c3.metric("성장률 (Speed)", f"{growth_val:+.2f}%", delta="증가" if growth_val>0 else "감소")
        c4.metric("가속도 (Accel)", f"{accel_val:+.2f}%p", delta="가속" if accel_val>0 else "감속")
        
        
        with st.chat_message("assistant"): st.write(ai_res)
        
        st.subheader("📊 12개월 선행 EPS 추세선")
        if not trend_df.empty:
            
            chart_data = trend_df.copy()
            chart_data.index = chart_data.index.strftime('%Y.%m')
            st.line_chart(chart_data)
        
        with st.expander("📋 원본 데이터 확인"):
            if not df_ui.empty: st.dataframe(df_ui.T)