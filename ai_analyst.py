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
          (규칙: '심각' 단계면 펀더멘털이 아무리 좋아도 '매도/현금화'를 최우선 권고.)
        - 경기 선행 지수(CLI) 추세: {cli_msg}
          (규칙: '회복 가속'은 경기민감주 매수 기회, '둔화 가속'은 방어주로 피신.)

        [2. 종목 펀더멘털 (AI 자체 지식 활용)]
        - **섹터 판단**: 이 종목이 경기민감주(Cyclical)인지 방어주(Defensive)인지 판단하세요.
        - **밸류에이션**: 현재 주가가 역사적 밸류에이션 대비 고평가/저평가 구간인지 판단하세요.

        [3. 이익 모멘텀 데이터]
        - 12M Fwd EPS: {fwd:,.2f}
        - 성장 속도(Growth): {growth:.2f}% (전월 대비)
        - 가속도(Accel): {accel_str} (성장폭의 변화)
        - 시스템 신호: {signal_msg}

        [4. 최종 투자 전략]
        위 모든 데이터를 종합하여 [강력 매수 / 매수 / 보유 / 매도 / 강력 매도] 중 하나의 의견을 제시하세요.
        
        결론 이유 3가지:
        1. 매크로(CLI/채권)와 섹터의 적합성.
        2. 이익 모멘텀(가속도) 분석 결과.
        3. 밸류에이션 매력도.
        
        **반드시 한국어로 답변해 주세요.**
        """
        return llm.invoke(prompt).content
    except Exception as e: return f"Error: {e}"