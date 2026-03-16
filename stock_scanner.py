import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股掃描器")

@st.cache_data(ttl=86400)
def get_all_tickers():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
    df = pd.read_html(resp.text)[0]
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    scanned_count = 0  # 確保計數器初始化
    
    batch_size = 30
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for i, batch in enumerate(batches):
        scanned_count += len(batch)
        progress_bar.progress((i + 1) / len(batches))
        progress_text.text(f"掃描中: {scanned_count} / {len(all_tickers)} 檔")
        
        try:
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 30: continue
                
                # 回溯機制
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    # 邏輯核心：恢復之前有效的篩選標準
                    vol_in_thousands = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_in_thousands < 5000: continue
                    
                    ma5 = df_sub['Volume'].rolling(window=5, min_periods=1).mean().iloc[-1]
                    ma20 = df_sub['Volume'].rolling(window=20, min_periods=1).mean().iloc[-1]
                    vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
                    
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9, fillna=True)
                    k = float(stoch.stoch().iloc[-1])
                    
                    # 篩選條件
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        curr_close = float(df['Close'].iloc[idx])
                        
                        if idx <= -4:
                            prev_close = float(df['Close'].iloc[idx-3])
                            three_day_gain = (curr_close - prev_close) / prev_close
                            if three_day_gain > 0.20:
                                results_3day.append({"代號": ticker.replace(".TW", ""), "訊號日期": signal_date, "漲幅": f"{three_day_gain:.1%}", "量比": round(vol_ratio, 2), "成交量(張)": int(vol_in_thousands)})
                        
                        six_mo_high = df_sub['Close'].rolling(120, min_periods=1).max().iloc[-1]
                        if curr_close >= six_mo_high:
                            results_6mo.append({"代號": ticker.replace(".TW", ""), "訊號日期": signal_date, "現價": round(curr_close, 2), "半年高點": round(six_mo_high, 2), "量比": round(vol_ratio, 2), "成交量(張)": int(vol_in_thousands)})
                        break 
            time.sleep(random.uniform(1, 2))
        except Exception:
            continue
            
    progress_text.success(f"掃描完成！共處理 {scanned_count} 檔股票。")
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

st.title("📊 飆股策略精準掃描器")
if st.button("啟動全市場掃描"):
    all_tickers = get_all_tickers()
    df_3day, df_6mo = scan_full_market(all_tickers)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚀 短線噴出")
        st.dataframe(df_3day, use_container_width=True)
    with col2:
        st.subheader("📈 中線突破")
        st.dataframe(df_6mo, use_container_width=True)
