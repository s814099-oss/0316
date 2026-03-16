import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 抑制 SSL 不安全請求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="台股穩定掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_target_tickers():
    """獲取上市股票清單"""
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    # 加入 verify=False 解決 SSL 錯誤
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
    df = pd.read_html(resp.text)[0]
    # 清洗：只選取 4 位數代號 (個股)
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_stocks(tickers):
    results = []
    # 限制測試數量，穩定後可移除 [:100]
    target_list = tickers[:100] 
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(target_list):
        progress.progress((i + 1) / len(target_list))
        status_text.text(f"正在掃描 ({i+1}/{len(target_list)}): {ticker}")
        
        try:
            # 使用 yf.Ticker 進行更穩定的單檔下載
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            
            if df.empty or len(df) < 20: continue
            
            # 計算簡單指標
            vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
            if vol_mean == 0: continue
            vol_ratio = df['Volume'].iloc[-1] / vol_mean
            
            if vol_ratio > 1.5:
                results.append({"代號": ticker, "量比": round(vol_ratio, 2)})
            
            # 隨機延遲，模仿人類行為，避免被 Yahoo 封鎖
            time.sleep(random.uniform(3, 5))
            
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results)

# --- UI 介面 ---
st.title("📊 台股穩定篩選器")
st.info("此版本已優化 SSL 連線與請求頻率，適合在雲端環境執行。")

if st.button("開始掃描前 100 檔"):
    with st.spinner("正在執行掃描，請稍候..."):
        try:
            tickers = get_target_tickers()
            df = scan_stocks(tickers)
            
            if not df.empty:
                st.success(f"掃描完成！共找到 {len(df)} 檔符合條件標的。")
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("掃描完成，無符合條件標的。")
        except Exception as e:
            st.error(f"發生系統錯誤: {e}")
