import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import requests
import re
import datetime
from io import StringIO

# logic.py에서 함수들 가져오기 (기존 프로젝트 구조 유지)
from logic import build_priority_map_kr, build_priority_map_us, calculate_12m_fwd_series

# -----------------------------------------------------------
# 1. 거시경제(Macro) 데이터 수집
# -----------------------------------------------------------
@st.cache_data(ttl=3600)
def get_macro_data():
    start_date = datetime.datetime.now() - datetime.timedelta(days=1000)
    
    # 1) FRED 데이터 (금리)
    try:
        y = web.DataReader('T10Y2Y', 'fred', start_date).dropna()
        h = web.DataReader('BAMLH0A0HYM2', 'fred', start_date).dropna()
    except: 
        y, h = pd.DataFrame(), pd.DataFrame()
    
    # 2) OECD CLI 데이터 (미국 & 한국)
    cli = pd.DataFrame()
    targets = {'USA': '미국_CLI', 'KOR': '한국_CLI'}
    
    for code, name in targets.items():
        try:
            url = f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/{code}.M.LI...AA...H?dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(StringIO(r.text))
                df['TIME_PERIOD'] = pd.to_datetime(df['TIME_PERIOD'])
                df = df.set_index('TIME_PERIOD').sort_index()
                cli[name] = df['OBS_VALUE']
        except Exception as e:
            print(f"{name} 로딩 실패: {e}")
            
    return y, h, cli

# -----------------------------------------------------------
# 2. 개별 주식 재무 데이터 수집 (한국: FnGuide, 미국: Yahoo)
# -----------------------------------------------------------
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
# [디버그용] 캐시 기능을 임시로 껐습니다.
def get_yahoo_data(ticker_code):
    import streamlit as st
    st.info(f"🐛 [디버그 1단계] 야후 파이낸스에 '{ticker_code}' 데이터 요청 시작...")
    
    try:
        stock = yf.Ticker(ticker_code)
        past_map, est_annual, est_quarter = {}, {}, {}
        
        # ---------------------------------------------------------
        # 🔍 검사 1: earnings_history (과거 실적)
        # ---------------------------------------------------------
        try:
            hist = stock.earnings_history
            if hist is None:
                st.error("🚨 [디버그: 과거 실적] earnings_history가 'None'으로 반환되었습니다. (야후가 막았음)")
            elif hist.empty:
                st.warning("⚠️ [디버그: 과거 실적] earnings_history는 응답했지만, 내용이 텅 비어있습니다 (Empty).")
            else:
                st.success("✅ [디버그: 과거 실적] 데이터를 성공적으로 받아왔습니다!")
                st.dataframe(hist) # 실제 어떤 데이터가 오는지 화면에 출력
                for idx, row in hist.iterrows():
                    if pd.notna(row['epsActual']):
                        past_map[(idx.year, (idx.month-1)//3+1)] = float(row['epsActual'])
        except Exception as e:
            st.error(f"❌ [디버그: 과거 실적] 코드 실행 중 에러 발생: {e}")

        # ---------------------------------------------------------
        # 🔍 검사 2: earnings_estimate (미래 추정치)
        # ---------------------------------------------------------
        try:
            est = stock.earnings_estimate
            if est is None:
                st.error("🚨 [디버그: 미래 실적] earnings_estimate가 'None'으로 반환되었습니다. (야후가 막았음)")
            elif est.empty:
                st.warning("⚠️ [디버그: 미래 실적] earnings_estimate는 응답했지만, 내용이 텅 비어있습니다 (Empty).")
            else:
                st.success("✅ [디버그: 미래 실적] 데이터를 성공적으로 받아왔습니다!")
                st.dataframe(est) # 실제 어떤 데이터가 오는지 화면에 출력
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
        except Exception as e:
            st.error(f"❌ [디버그: 미래 실적] 코드 실행 중 에러 발생: {e}")

        # 최종 추출된 데이터 개수 요약
        st.info(f"📝 [디버그 최종 결과] 확보된 과거 EPS: {len(past_map)}개 / 확보된 미래 EPS: {len(est_annual)}개")
        
        return past_map, est_annual, est_quarter
        
    except Exception as e:
        import streamlit as st
        st.error(f"🚨 [디버그 치명적 에러] get_yahoo_data 전체가 뻗었습니다: {e}")
        return {}, {}, {}

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

# -----------------------------------------------------------
# 3. 🛡️ 3중 방어 티커 검색 시스템 (핵심 개선 사항)
# -----------------------------------------------------------
@st.cache_data(ttl=86400) # 하루(86400초) 동안 CSV 데이터 캐싱
def get_krx_csv_cache():
    try:
        # fdr 대신 안정적인 KRX 전체 목록 CSV 파일을 읽어옵니다.
        url = "https://raw.githubusercontent.com/corazzon/finance-data-analysis/main/krx.csv"
        df = pd.read_csv(url, dtype={'Symbol': str}) 
        df['CleanName'] = df['Name'].astype(str).str.replace(" ", "").str.upper()
        return df
    except Exception as e:
        print(f"⚠️ CSV 백업 로딩 실패: {e}")
        return None

def find_ticker(user_input):
    original_input = user_input.strip()
    clean_input = original_input.replace(" ", "").upper()
    
    # [1단계] 하드코딩 사전
    mapping = {
        "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "팔란티어":"PLTR",
        "구글": "GOOGL", "아마존": "AMZN", "메타": "META", "브로드컴": "AVGO",
        "티에스엠": "TSM", "AMD": "AMD", "인텔": "INTC", "마이크론": "MU",
        "스타벅스": "SBUX", "코카콜라": "KO", "나이키": "NKE", "리얼티인컴": "O",
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "카카오": "035720.KS", "네이버": "035420.KS",
        "현대차": "005380.KS", "기아": "000270.KS"
    }
    
    for key, val in mapping.items():
        if key.replace(" ", "").upper() == clean_input:
            country = "KR" if (".KS" in val or ".KQ" in val) else "US"
            return val, original_input, country

    # [2단계] 안정적인 CSV 백업본 직접 호출 (한국 주식 찾기)
    krx_df = get_krx_csv_cache()
    if krx_df is not None:
        match = krx_df[krx_df['CleanName'] == clean_input]
        if not match.empty:
            code = str(match.iloc[0]['Symbol']).zfill(6)
            mkt = str(match.iloc[0].get('Market', 'KOSPI')).upper()
            suffix = ".KQ" if 'KOSDAQ' in mkt else ".KS"
            return f"{code}{suffix}", original_input, "KR"

    # [3단계] 최후의 보루 야후 파이낸스 자체 검색 API
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={original_input}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            quotes = res.json().get('quotes', [])
            if quotes:
                for q in quotes:
                    sym = q.get('symbol', '')
                    if sym.endswith('.KS') or sym.endswith('.KQ'):
                        return sym, original_input, "KR"
                
                first_sym = quotes[0].get('symbol', '')
                return first_sym, original_input, "US"
    except Exception as e:
        print(f"🚨 야후 검색 API 실패: {e}")

    # 다 실패하면 사용자가 직접 입력한 값 그대로 리턴
    return original_input.upper(), original_input, "US"
