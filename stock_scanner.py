import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

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
    
    batch_size = 30
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        try:
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 125: continue
                
                # 回溯檢查最近 7 天
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    # 1. 成交量門檻：1,000 張 (1,000,000 股)
                    current_volume_shares = float(df_sub['Volume'].iloc[-1])
                    if current_volume_shares < 1000000: continue
                    
                    # 2. 技術指標檢查
                    vol_ratio = (df_sub['Volume'].rolling(5).mean().iloc[-1]) / (df_sub['Volume'].rolling(20).mean().iloc[-1])
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9)
                    k = float(stoch.stoch().iloc[-1])
                    
                    # 共同門檻：量比 > 1.85 且 K > 80
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        curr_close = float(df['Close'].iloc[idx])
                        
                        # 策略 A: 短線噴出 (3天漲幅 > 20%)
                        if idx <= -4:
                            prev_close = float(df['Close'].iloc[idx-3])
                            three_day_gain = (curr_close - prev_close) / prev_close
                            if three_day_gain > 0.20:
                                results_3day.append({"代號": ticker.replace(".TW", ""), "訊號日期": signal_date, "漲幅": f"{three_day_gain:.1%}", "量比": round(vol_ratio, 2), "成交量(張)": int(current_volume_shares / 1000)})
                        
                        # 策略 B: 中線突破 (半年新高)
                        six_mo_high = df_sub['Close'].rolling(120).max().iloc[-1]
                        if curr_close >= six_mo_high:
                            results_6mo.append({"代號": ticker.replace(".TW", ""), "訊號日期": signal_date, "現價": round(curr_close, 2), "半年高點": round(six_mo_high, 2), "量比": round(vol_ratio, 2), "成交量(張)": int(current_volume_shares / 1000)})
                        
                        break 
            time.sleep(random.uniform(2, 4))
        except Exception:
            continue
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# UI 介面
st.title("📊 飆股策略精準掃描器")
if st.button("啟動全市場掃描"):
    with st.spinner("掃描中，請稍候..."):
        all_tickers = get_all_tickers()
        df_3day, df_6mo = scan_full_market(all_tickers)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚀 短線噴出 (3天漲幅 > 20%)")
            st.dataframe(df_3day, use_container_width=True)
        with col2:
            st.subheader("📈 中線突破 (半年新高)")
            st.dataframe(df_6mo, use_container_width=True)
