import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator
from datetime import datetime

# 強制繞過 SSL 憑證檢查
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股飆股進階掃描", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=10)
            df = pd.read_html(resp.text)[0]
            df = df.iloc[1:, [0]]
            df.columns = ['代號名稱']
            df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
            all_tickers.extend([f"{t}.TW" for t in df['代號'].dropna().unique()])
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers):
    results_gain = []
    results_high = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {min((i+1)*batch_size, len(tickers))} / {len(tickers)} 檔")
        
        try:
            time.sleep(random.uniform(1.0, 1.5))
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=True)
            
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 125: continue # 確保有半年資料
                
                # 計算指標
                curr = df.iloc[-1]
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                if vol20 == 0: continue
                vol_ratio = vol5 / vol20
                
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 篩選條件 1: 量比 > 1.85, K > 80, 3天漲幅 > 20%
                three_day_gain = (df['Close'].iloc[-1] - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                if vol_ratio > 1.85 and k_val > 80 and three_day_gain > 0.20:
                    results_gain.append({"代號": s.replace(".TW", ""), "現價": round(float(curr['Close']), 2), "漲幅": f"{round(three_day_gain*100, 2)}%", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                
                # 篩選條件 2: 量比 > 1.85, K > 80, 半年新高
                six_mo_high = df['Close'].rolling(120).max().iloc[-1]
                if vol_ratio > 1.85 and k_val > 80 and float(curr['Close']) >= six_mo_high:
                    results_high.append({"代號": s.replace(".TW", ""), "現價": round(float(curr['Close']), 2), "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    
        except Exception: continue
            
    return pd.DataFrame(results_gain), pd.DataFrame(results_high)

# --- UI 介面 ---
st.title("📊 台股飆股進階掃描器")

if st.button("啟動全面掃描"):
    all_tickers = get_all_tickers()
    df1, df2 = run_scanner(all_tickers)
    
    tab1, tab2 = st.tabs(["🚀 短線強勢 (3天漲幅 > 20%)", "📈 中線突破 (半年新高)"])
    
    with tab1:
        if not df1.empty:
            st.dataframe(df1.sort_values("漲幅", ascending=False), use_container_width=True)
        else:
            st.info("目前無符合 3 天強勢飆漲條件的標的")
            
    with tab2:
        if not df2.empty:
            st.dataframe(df2.sort_values("量比", ascending=False), use_container_width=True)
        else:
            st.info("目前無符合半年新高突破條件的標的")
