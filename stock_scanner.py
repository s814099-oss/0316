import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator
from datetime import datetime, timedelta

# 繞過 SSL
ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="台股分組掃描器", layout="wide")

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
    res_20pct, res_high = [], []
    batch_size = 20 # 恢復你喜歡的 20 檔一組
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"正在處理第 {i+1} / {len(batches)} 組...")
        
        try:
            # 加入間隔，避免 Yahoo 瞬間判定為惡意爬蟲
            time.sleep(3.0) 
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=False)
            
            # 關鍵點：必須確認回傳的是 DataFrame 且不是空的
            if data.empty: continue
            
            for s in batch:
                # 避開下載失敗的代號
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 120: continue 
                
                cur_vol = float(df['Volume'].iloc[-1])
                if cur_vol < (min_vol * 1000): continue
                
                # 計算指標
                vol_ratio = df['Volume'].rolling(5).mean().iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                if vol_ratio > 1.85 and k_val > 80:
                    cur_close = float(df['Close'].iloc[-1])
                    # 條件 1
                    if (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4] >= 0.20:
                        res_20pct.append({"代號": s.replace(".TW", ""), "現價": cur_close, "漲幅": "20%+", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    # 條件 2
                    if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                        res_high.append({"代號": s.replace(".TW", ""), "現價": cur_close, "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
        except:
            continue # 遇到這組有錯直接跳下一組，不讓程式死掉
            
    return pd.DataFrame(res_20pct), pd.DataFrame(res_high)

# UI 設定
st.title("🔥 台股精準分組掃描")
min_vol = st.sidebar.number_input("最低成交量 (張)", value=500)

if st.button("啟動掃描"):
    all_tickers = get_all_tickers()
    df20, dfH = run_scanner(all_tickers, min_vol)
    
    tab1, tab2 = st.tabs(["🚀 指標 + 3天漲20%", "📈 指標 + 半年新高"])
    with tab1: st.dataframe(df20, use_container_width=True)
    with tab2: st.dataframe(dfH, use_container_width=True)
