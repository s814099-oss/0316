import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 環境設定
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
    
    # 直接在畫面上建立進度與文字
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(all_tickers):
        progress = (i + 1) / len(all_tickers)
        progress_bar.progress(progress)
        status_text.text(f"掃描進度: {i+1}/{len(all_tickers)} | 正在檢查: {ticker}")
        
        try:
            df = yf.download(ticker, period="6mo", interval="1d", threads=False, progress=False)
            if df.empty or len(df) < 30: continue
            
            vol_raw = float(df['Volume'].iloc[-1])
            vol_in_zhang = vol_raw / 1000 if vol_raw > 100000 else vol_raw
            
            if vol_in_zhang < 5000: continue
            
            ma5 = df['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
            ma20 = df['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
            vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, fillna=True)
            k = float(stoch.stoch().iloc[-1])
            
            if vol_ratio > 1.85 and k > 80:
                results.append({"代號": ticker.replace(".TW", ""), "成交量(張)": int(vol_in_zhang), "量比": round(vol_ratio, 2), "K值": round(k, 2)})
            
            time.sleep(0.1) # 極短暫延遲防止伺服器封鎖
        except:
            continue
            
    status_text.success("掃描完成！")
    return pd.DataFrame(results)

st.title("📊 飆股策略精準掃描器")
if st.button("啟動全市場掃描"):
    all_tickers = get_all_tickers()
    df_results = scan_full_market(all_tickers)
    if not df_results.empty:
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("本次掃描未發現符合條件的股票。")
