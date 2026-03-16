import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
from ta.momentum import StochasticOscillator

# 1. 強化版代號獲取：直接過濾掉權證(長度 > 4)與非個股標的
@st.cache_data(ttl=86400)
def get_clean_tickers():
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    clean_list = []
    for url in urls:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            df = pd.read_html(resp.text)[0]
            # 只取 4 位數代號 (個股)
            tickers = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)].iloc[:, 0]
            clean_list.extend([f"{t.split()[0]}.TW" for t in tickers])
        except: continue
    return list(set(clean_list))

# 2. 加入「冷卻模式」的掃描引擎
def run_scanner_pro(tickers):
    results = []
    # 每次只抓 5 檔，大幅降低被封鎖機率
    batch_size = 5 
    
    progress = st.progress(0)
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        progress.progress(i / len(tickers))
        
        try:
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', progress=False)
            
            for s in batch:
                # 若 data 是空的或該股無資料，直接跳過
                df = data[s] if len(batch) > 1 else data
                if df.empty or len(df) < 20: continue
                
                # 計算指標 (簡化版)
                vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9)
                k = float(stoch.stoch().iloc[-1])
                
                if vol_ratio > 1.5 and k > 75:
                    results.append({"代號": s, "量比": round(vol_ratio, 2), "K值": round(k, 2)})
            
            # 動態冷卻：每批次後隨機休息 3-6 秒
            time.sleep(random.uniform(3, 6))
            
        except Exception as e:
            if "429" in str(e):
                time.sleep(60) # 被鎖了？強制冷卻 1 分鐘
            continue
            
    return pd.DataFrame(results)

# --- UI ---
if st.button("啟動優化版掃描"):
    tickers = get_clean_tickers()
    st.write(f"已過濾出 {len(tickers)} 檔個股，開始掃描...")
    df_res = run_scanner_pro(tickers)
    st.dataframe(df_res)
