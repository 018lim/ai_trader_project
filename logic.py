import pandas as pd
import datetime

# [핵심 1] 12M Fwd EPS 계산 (월별 가중치 Rolling)
def calculate_12m_fwd_series(q_map):
    if not q_map: return pd.DataFrame()
    
    dates = pd.date_range(end=datetime.date.today(), periods=13, freq='ME')
    trend_data = []

    for d in dates:
        fwd_eps_sum = 0
        valid_months = 0
        for i in range(12):
            target_date = d + pd.DateOffset(months=i+1)
            y = target_date.year
            m = target_date.month
            q = (m - 1) // 3 + 1
            q_eps = q_map.get((y, q))
            if q_eps is not None:
                fwd_eps_sum += (q_eps / 3)
                valid_months += 1
        
        if valid_months >= 6:
            trend_data.append(fwd_eps_sum * (12 / valid_months))
        else:
            trend_data.append(0)

    return pd.DataFrame({'12M Fwd EPS': trend_data}, index=dates)

# [핵심 2] CLI 추세 정밀 분석 (3개월치 비교)
def analyze_cli_trend(curr, prev, pprev):
    diff_now = curr - prev
    diff_prev = prev - pprev
    
    status_msg = ""
    color = "gray"
    
    # 경기 수축/회복 국면 (100 이하)
    if curr <= 100:
        if diff_now > 0:
            if diff_now > diff_prev:
                status_msg = "🚀 회복 가속 (바닥 탈출 강력)"
                color = "green"
            else:
                status_msg = "📈 회복 중 (속도 둔화)"
                color = "blue"
        else:
            if diff_now > diff_prev:
                status_msg = "📉 하락폭 축소 (바닥 근접)"
                color = "orange"
            else:
                status_msg = "❄️ 침체 심화 (하락 가속)"
                color = "red"
                
    # 경기 확장/둔화 국면 (100 초과)
    else:
        if diff_now > 0:
            if diff_now > diff_prev:
                status_msg = "🔥 호황 가속 (과열 주의)"
                color = "red"
            else:
                status_msg = "☁️ 확장 중 (탄력 둔화)"
                color = "orange"
        else:
            if diff_now < diff_prev:
                status_msg = "☔️ 둔화 가속 (본격 하락)"
                color = "blue"
            else:
                status_msg = "📉 완만한 조정"
                color = "gray"
                
    return status_msg, color

# [핵심 3] 데이터 우선순위 병합 (Adapter)
def build_priority_map_kr(df_raw):
    q_map = {}
    if df_raw is None or df_raw.empty: return q_map
    data_dict = df_raw.iloc[0].to_dict()
    for k, v in data_dict.items():
        if "A|" in str(k) and "Blended" not in str(k):
            try:
                yr = int(k.replace("A|", "").split('/')[0])
                for q in range(1, 5): q_map[(yr, q)] = float(v) / 4
            except: pass
    for k, v in data_dict.items():
        if "Q|" in str(k):
            try:
                parts = k.replace("Q|", "").split('/')
                yr, mo = int(parts[0]), int(parts[1])
                q_map[(yr, (mo-1)//3+1)] = float(v)
            except: pass
    return q_map

def build_priority_map_us(past_map, est_annual, est_quarter):
    q_map = {}
    for yr, val in est_annual.items():
        for q in range(1, 5): q_map[(yr, q)] = val / 4
    for (yr, q), val in est_quarter.items(): q_map[(yr, q)] = val
    for (yr, q), val in past_map.items(): q_map[(yr, q)] = val
    return q_map