import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 1. 環境設定
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
    results = []
    scanned_count = 0
    
    # 建立進度顯示
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    # 逐檔處理，避免多執行緒導致的 Runtime Error
    for ticker in all_tickers:
        scanned_count += 1
        progress_bar.progress(scanned_count / len(all_tickers))
        progress_text.text(f"正在掃描: {scanned_count} / {len(all_tickers)} 檔 - {ticker}")
        
        try:
            # 關閉 threads 以解決線程衝突
            df = yf.download(ticker, period="6mo", interval="1d", threads=False, progress=False)
            if df.empty or len(df) < 30: continue
            
            # --- 核心：動態單位檢測 ---
            vol_raw = float(df['Volume'].iloc[-1])
            # 如果這檔股票成交量看起來像股數(數值巨大)，則除以1000轉為張
            vol_in_zhang = vol_raw / 1000 if vol_raw > 100000 else vol_raw
            
            # 篩選條件：成交量 > 5000 張
            if vol_in_zhang < 5000: continue
            
            # 技術指標
            ma5 = df['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
            ma20 = df['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
            vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, fillna=True)
            k = float(stoch.stoch().iloc[-1])
            
            # 篩選：量比 > 1.85 且 K > 80
            if vol_ratio > 1.85 and k > 80:
                results.append({
                    "代號": ticker.replace(".TW", ""), 
                    "成交量(張)": int(vol_in_zhang),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k, 2)
                })
            
            # 避免對 Yahoo 請求過快被封鎖
            time.sleep(0.5)
            
        except Exception:
            continue
            
    progress_text.success(f"掃描完成！共處理 {len(all_tickers)} 檔股票。")
    return pd.DataFrame(results)

# UI 介面
st.title("📊 飆股策略精準掃描器")
if st.button("啟動全市場掃描"):
    with st.spinner("正在進行全市場掃描，請稍候..."):
        all_tickers = get_all_tickers()
        df_results = scan_full_market(all_tickers)
        if not df_results.empty:
            st.dataframe(df_results, use_container_width=True)
        else:
            st.warning("本次掃描未發現符合條件的股票，請嘗試調整篩選條件。")
