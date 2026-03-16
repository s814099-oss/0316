import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator
from datetime import datetime, timedelta

# 強制繞過 SSL
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股精準掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=10)
            df = pd.read_html(resp.text)[0]
            df = df.iloc[1:, [0]]
            df['代號'] = df.iloc[:, 0].str.extract(r'^(\d{4})\s')
            all_tickers.extend([f"{t}.TW" for t in df['代號'].dropna().unique()])
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers, min_vol):
    res_20pct = [] # 條件: 量比>1.85, K>80, 3天漲幅>20%
    res_high = []  # 條件: 量比>1.85, K>80, 半年新高
    
    total_count = len(tickers)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    batch_size = 10 
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        elapsed = time.time() - start_time
        eta_sec = (len(batches) - (i + 1)) * (elapsed / (i + 1)) if i > 0 else 300
        eta_str = str(timedelta(seconds=int(eta_sec)))
        status_text.text(f"掃描進度: {min((i+1)*batch_size, total_count)}/{total_count} | 預計剩餘: {eta_str}")
        
        try:
            time.sleep(random.uniform(3.0, 5.0))
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=False)
            
            for s in batch:
                if s not in data: continue
                df = data[s].dropna()
                if len(df) < 120 or float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
                
                # 計算指標
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                if vol20 == 0: continue
                vol_ratio = vol5 / vol20
                
                # 僅計算 K 值 (StochasticOscillator)
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 核心篩選條件: 量比 > 1.85 且 K值 > 80
                if vol_ratio > 1.85 and k_val > 80:
                    cur_close = float(df['Close'].iloc[-1])
                    
                    # 策略 1: 3天漲幅 > 20%
                    three_day_gain = (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                    if three_day_gain >= 0.20:
                        res_20pct.append({"代號": s.replace(".TW", ""), "現價": cur_close, "漲幅": f"{three_day_gain:.2%}", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    
                    # 策略 2: 半年新高
                    if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                        res_high.append({"代號": s.replace(".TW", ""), "現價": cur_close, "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    
        except Exception as e:
            if "Too Many Requests" in str(e): time.sleep(60)
            continue
    
    return pd.DataFrame(res_20pct), pd.DataFrame(res_high)

st.title("🔥 台股精準策略掃描 (量比>1.85, K>80)")
min_vol = st.sidebar.number_input("最低成交量 (張)", value=500)

if st.button("開始掃描"):
    all_tickers = get_all_tickers()
    df20, dfH = run_scanner(all_tickers, min_vol)
    
    tab1, tab2 = st.tabs(["🚀 指標 + 3天漲20%", "📈 指標 + 半年新高"])
    with tab1:
        st.dataframe(df20, use_container_width=True)
    with tab2:
        st.dataframe(dfH, use_container_width=True)
