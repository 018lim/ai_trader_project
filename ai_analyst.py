import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI

def ask_ai(ticker, name, fwd, growth, accel_str, bond_msg, cli_msg, signal_msg):
    # Streamlit Cloud의 Secrets 또는 로컬 환경변수 사용
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API Key가 설정되지 않았습니다. (Secrets 설정 필요)"

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=api_key)
        prompt = f"""
        당신은 월가의 전설적인 펀드매니저입니다. '{name}({ticker})' 종목을 정밀 분석해 주세요.

        [1. 매크로 위험 평가 (Critical Rules)]
        - 채권 시장 상태: {bond_msg}
          
        - 경기 선행 지수(CLI) 추세: {cli_msg}
          

        [2. 종목 펀더멘털 (AI 자체 지식 활용)]
        - **섹터 판단**: 이 종목이 경기민감주(Cyclical)인지 방어주(Defensive)인지 판단하세요.
        - {ticker}의 선행 PER을 검색해서 평가해. 
        

        [3. 이익 모멘텀 데이터]
        - 12M Fwd EPS: {fwd:,.2f}
        - 성장 속도(Growth): {growth:.2f}% (전월 대비)
        - 가속도(Accel): {accel_str} (성장폭의 변화)
        - 시스템 신호: {signal_msg}

        [4. 최종 투자 전략]
        이 글은 투자권유가 아니며 투자의 책임은 본인에게 있습니다. 이글을 맨 앞에 명시해.
        너의 결론은 먼저 짧게 말하고 굵은 글씨로 써.
        경기 민감주는 메크로 위험평가에 가중을 더 두고, 경기 방어주는 메크로 위험 평가 가중을 덜 줘.
        
        결론 이유 3가지:
        1. 매크로(CLI/채권)와 섹터의 적합성.
        2. 이익 모멘텀(가속도) 분석 결과.
        3. {ticker}의 선행 PER을 고려해.
        
        
        **반드시 한국어로 답변해 주세요.**
        """
        return llm.invoke(prompt).content
    except Exception as e: return f"Error: {e}"