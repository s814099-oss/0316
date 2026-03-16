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
st.set_page_config(page_title="台股精準指標掃描", layout="wide")

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
    res_explosion = [] # 量比>1.85 & K>80 & 3天漲幅>20%
    res_breakout = []  # 量比>1.85 & K>80 & 半年新高
    total_count = len(tickers)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for i, batch in enumerate(batches):
        elapsed = time.time() - start_time
        avg_time = elapsed / (i + 1)
        eta_sec = (len(batches) - (i + 1)) * avg_time
        eta_str = str(timedelta(seconds=int(eta_sec)))
        
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {min((i+1)*batch_size, total_count)}/{total_count} | 預計剩餘: {eta_str}")
        
        try:
            time.sleep(random.uniform(1.2, 1.8))
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=True)
            
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 120: continue 
                
                # 1. 成交量門檻
                if float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
                
                # 2. 計算核心指標 (量比與K值)
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                if vol20 == 0: continue
                
                vol_ratio = vol5 / vol20
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 3. 核心指標過濾
                if vol_ratio > 1.85 and k_val > 80:
                    cur_close = float(df['Close'].iloc[-1])
                    
                    # 策略 A: 3天漲幅 > 20%
                    three_day_gain = (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                    if three_day_gain >= 0.20:
                        res_explosion.append({"代號": s.replace(".TW", ""), "現價": cur_close, "漲幅": f"{three_day_gain:.2%}", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    
                    # 策略 B: 半年新高 (收盤價為近120日最高)
                    if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                        res_breakout.append({"代號": s.replace(".TW", ""), "現價": cur_close, "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                        
        except: continue
    
    return pd.DataFrame(res_explosion), pd.DataFrame(res_breakout)

# --- UI ---
st.title("📊 精準選股：技術指標 + 雙維度篩選")
min_vol = st.sidebar.number_input("最低成交量 (張)", value=500)

if st.button("啟動掃描 (量比>1.85, K>80)"):
    tickers = get_all_tickers()
    df_exp, df_break = run_scanner(tickers, min_vol)
    
    tab1, tab2 = st.tabs(["🚀 強勢噴發 (指標 + 3天漲20%)", "📈 強勢突破 (指標 + 半年新高)"])
    with tab1:
        st.dataframe(df_exp, use_container_width=True)
    with tab2:
        st.dataframe(df_break, use_container_width=True)
