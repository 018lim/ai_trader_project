import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import FinanceDataReader as fdr
import requests
import re
import datetime
from io import StringIO
# logic.py에서 함수들 가져오기
from logic import build_priority_map_kr, build_priority_map_us, calculate_12m_fwd_series

@st.cache_data(ttl=3600)
def get_macro_data():
    start_date = datetime.datetime.now() - datetime.timedelta(days=1000)
    
    # 1. FRED 데이터 (금리)
    try:
        y = web.DataReader('T10Y2Y', 'fred', start_date).dropna()
        h = web.DataReader('BAMLH0A0HYM2', 'fred', start_date).dropna()
    except: 
        y, h = pd.DataFrame(), pd.DataFrame()
    
    # 2. OECD CLI 데이터 (미국 & 한국)
    cli = pd.DataFrame()
    # OECD DSD_STES 데이터셋: LLI(Leading Indicators), AA(Amplitude Adjusted)
    targets = {'USA': '미국_CLI', 'KOR': '한국_CLI'}
    
    for code, name in targets.items():
        try:
            # OECD 최신 API 경로 (데이터 구조 복구용)
            url = f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/{code}.M.LI...AA...H?dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(StringIO(r.text))
                # 데이터 필터링 및 전처리
                df['TIME_PERIOD'] = pd.to_datetime(df['TIME_PERIOD'])
                df = df.set_index('TIME_PERIOD').sort_index()
                cli[name] = df['OBS_VALUE']
        except Exception as e:
            print(f"{name} 로딩 실패: {e}")
            
    return y, h, cli

@st.cache_data(ttl=3600)
def get_fnguide_data(ticker_code):
    code = re.sub(r'[^0-9]', '', ticker_code)
    url = f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(StringIO(r.text))
        merged = {}
        for df in tables:
            if any(df.iloc[:, 0].astype(str).str.contains("EPS|주당순이익")):
                row = df[df.iloc[:, 0].astype(str).str.contains("EPS|주당순이익")].iloc[0]
                for i, col in enumerate(df.columns):
                    if i == 0: continue
                    date_match = re.search(r"(\d{4}/\d{2})", str(col))
                    if date_match:
                        is_quarter = "분기" in str(df.columns) or "Quarter" in str(df.columns)
                        tag = "Q|" if is_quarter else "A|"
                        val = str(row.iloc[i]).replace(',', '').split('(')[0]
                        if val.strip() not in ['-', '', 'nan', 'N/A']:
                            merged[f"{tag}{date_match.group(1)}"] = int(float(val))
        return pd.DataFrame([merged], index=['EPS']) if merged else None
    except: return None

@st.cache_data(ttl=3600)
def get_yahoo_data(ticker_code):
    try:
        stock = yf.Ticker(ticker_code)
        past_map, est_annual, est_quarter = {}, {}, {}
        
        hist = stock.earnings_history
        if hist is not None:
            for idx, row in hist.iterrows():
                if pd.notna(row['epsActual']):
                    past_map[(idx.year, (idx.month-1)//3+1)] = float(row['epsActual'])
        
        est = stock.earnings_estimate
        if est is not None:
            est.index = est.index.astype(str).str.strip()
            curr_y = datetime.date.today().year
            for term, offset in [('0y',0), ('+1y',1), ('+5y',5)]:
                if term in est.index:
                    val = est.loc[term, 'avg']
                    if pd.notna(val): est_annual[curr_y+offset] = float(val)
            
            if '0q' in est.index:
                val = est.loc['0q', 'avg']
                if pd.notna(val): est_quarter[(curr_y, (datetime.date.today().month-1)//3+1)] = float(val)
            if '+1q' in est.index:
                val = est.loc['+1q', 'avg']
                if pd.notna(val):
                    nm = datetime.date.today().month + 3
                    ny = curr_y + (1 if nm > 12 else 0)
                    nq = ((nm-1)//3+1) if nm <= 12 else 1
                    est_quarter[(ny, nq)] = float(val)

        return past_map, est_annual, est_quarter
    except: return {}, {}, {}

@st.cache_data(ttl=3600)
def get_unified_data(ticker, country_code):
    merged_ui = {}
    trend_df = pd.DataFrame()
    
    if country_code == "KR":
        df_raw = get_fnguide_data(ticker)
        if df_raw is not None:
            q_map = build_priority_map_kr(df_raw)
            trend_df = calculate_12m_fwd_series(q_map)
            merged_ui = df_raw.iloc[0].to_dict()
    else:
        past, est_a, est_q = get_yahoo_data(ticker)
        q_map = build_priority_map_us(past, est_a, est_q)
        trend_df = calculate_12m_fwd_series(q_map)
        
        if est_a:
            curr_y = datetime.date.today().year
            if curr_y in est_a: merged_ui['A|ThisYear'] = est_a[curr_y]
        sorted_past = sorted(past.keys())[-4:]
        for y, q in sorted_past: merged_ui[f"Q|{y}.{q}Q"] = past[(y,q)]

    df_ui = pd.DataFrame([merged_ui], index=['EPS']) if merged_ui else pd.DataFrame()
    return df_ui, trend_df

def find_ticker(user_input):
    mapping = {
        "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "팔란티어":"PLTR",
        "구글": "GOOGL", "아마존": "AMZN", "메타": "META", "브로드컴": "AVGO",
        "티에스엠": "TSM", "AMD": "AMD", "인텔": "INTC", "마이크론": "MU",
        "스타벅스": "SBUX", "코카콜라": "KO", "나이키": "NKE", "리얼티인컴": "O"
    }
    user_input = user_input.strip()
    if user_input in mapping: return mapping[user_input], f"{user_input} ({mapping[user_input]})", "US"
    try:
        df_krx = fdr.StockListing('KRX')
        match = df_krx[df_krx['Name'] == user_input]
        if not match.empty:
            code = match.iloc[0]['Code']
            mkt = match.iloc[0]['Market']
            suffix = ".KS" if mkt == 'KOSPI' else ".KQ"
            return f"{code}{suffix}", user_input, "KR"
    except: pass
    return user_input.upper(), user_input, "US"