import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests

st.set_page_config(layout="wide")

@st.cache_data(ttl=86400)
def get_target_tickers():
    # 簡化版：只抓取上市個股，減少無效清單
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    df = pd.read_html(resp.text)[0]
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_stocks(tickers):
    results = []
    # 限制每次處理的數量，避免記憶體溢出
    subset = tickers[:100] 
    progress = st.progress(0)
    
    for i, ticker in enumerate(subset):
        progress.progress(i / len(subset))
        try:
            # 每次單獨請求一檔，雖然慢，但絕對穩
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            
            if len(df) < 20: continue
            
            # 計算簡單指標
            vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
            if vol_ratio > 1.5:
                results.append({"代號": ticker, "量比": round(vol_ratio, 2)})
            
            time.sleep(random.uniform(2, 4)) # 穩定且必要的間隔
            
        except Exception:
            continue
    return pd.DataFrame(results)

st.title("📊 台股穩定篩選器")
if st.button("開始執行穩定篩選 (前100檔)"):
    with st.spinner("正在逐檔檢查，請耐心等待..."):
        tickers = get_target_tickers()
        df = scan_stocks(tickers)
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("目前無符合條件標的")
