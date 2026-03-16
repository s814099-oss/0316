import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# 繞過 SSL 驗證，解決 CERTIFICATE_VERIFY_FAILED
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股全市場掃描器 (SSL 修復版)", layout="wide")

@st.cache_data(ttl=86400)
def get_all_stock_tickers():
    # 使用 requests 取得，並確保 Header 偽裝成瀏覽器，避免被擋
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, verify=False)
        df = pd.read_html(response.text)[0]
        # 篩選出上市股票 (代碼通常在第 1 欄，名稱在第 2 欄)
        # 證交所表格第一列是標題，我們從第二列開始
        df = df.iloc[1:, [0, 1]]
        df.columns = ['代號名稱', 'ISIN']
        # 提取前 4 碼
        df['代號'] = df['代號名稱'].str.extract(r'(\d{4})')
        # 過濾空值
        tickers = df['代號'].dropna().unique().tolist()
        return [f"{t}.TW" for t in tickers]
    except Exception as e:
        st.error(f"錯誤代碼: {e}")
        return []

def scan_stocks(tickers):
    results = []
    st.write(f"系統已載入 {len(tickers)} 檔股票，開始進行全市場掃描...")
    progress_bar = st.progress(0)
    
    # 這裡將總量限制在 100 檔以內進行測試，避免一開始就噴出錯誤
    for i, s in enumerate(tickers[:100]):
        progress_bar.progress((i + 1) / 100)
        try:
            time.sleep(random.uniform(0.3, 0.6))
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if df.empty or len(df) < 20: continue
            
            price = float(df['Close'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            if vol20 == 0: continue
            
            vol_ratio = vol5 / vol20
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'])
            k_val = float(stoch.stoch().iloc[-1])
            
            if vol_ratio > 1.2 and k_val > 60:
                results.append({"股票": s.replace(".TW", ""), "價格": round(price, 2), "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
        except: continue
    return pd.DataFrame(results)

st.title("📊 台股全市場飆股掃描器")
if st.button("啟動全市場掃描"):
    all_tickers = get_all_stock_tickers()
    if all_tickers:
        df_res = scan_stocks(all_tickers)
        if not df_res.empty:
            st.dataframe(df_res.sort_values(by="量比", ascending=False), width=None)
        else:
            st.warning("無符合條件標的。")
    else:
        st.error("清單抓取失敗，請確認網路環境。")
