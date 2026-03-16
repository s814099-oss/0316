import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# 強制繞過 SSL 憑證檢查
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="台股全市場飆股掃描器", layout="wide")

# 1. 自動抓取證交所「所有」上市股票代碼
@st.cache_data(ttl=86400)
def get_all_tickers():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        df = pd.read_html(response.text)[0]
        df = df.iloc[1:, [0, 1]]
        df.columns = ['代號名稱', 'ISIN']
        # 提取代碼並確保是 4 位數字的股票 (排除權證、ETF)
        df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
        tickers = df['代號'].dropna().unique().tolist()
        return [f"{t}.TW" for t in tickers]
    except Exception as e:
        st.error(f"清單獲取失敗: {e}")
        return []

# 2. 核心掃描運算
def run_scanner(tickers):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    
    # 開始掃描所有股票
    for i, s in enumerate(tickers):
        progress_bar.progress((i + 1) / total)
        # 每 10 檔更新一次文字，減少網頁負擔
        if i % 10 == 0:
            status_text.text(f"進度: {i+1}/{total} | 正在分析: {s}")
        
        try:
            # 必須保留微小延遲，否則會被 Yahoo 封鎖 IP
            time.sleep(0.1) 
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 25:
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 數值計算
            price = float(df['Close'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            if vol20 == 0: continue
            vol_ratio = vol5 / vol20
            
            # KD 指標 (標準 9, 3, 3)
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # 你的核心篩選條件 (可自行微調)
            if vol_ratio > 1.85 and k_val > 80:
                results.append({
                    "股票代號": s.replace(".TW", ""),
                    "目前價格": round(price, 2),
                    "5日均量": int(vol5),
                    "量比(5/20)": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except:
            continue
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# 3. 網頁介面
st.title("🔥 台股全市場飆股自動掃描 (解鎖版)")
st.info("警告：全市場掃描（約 1000+ 檔）需耗時約 10-15 分鐘，請保持網頁開啟不要重新整理。")

if st.button("啟動全市場深度掃描"):
    all_tickers = get_all_tickers()
    if all_tickers:
        # 這裡已經移除限制，會跑完 all_tickers 裡面的每一檔
        df_res = run_scanner(all_tickers)
        
        if not df_res.empty:
            st.success(f"掃描完畢！在 {len(all_tickers)} 檔中發現 {len(df_res)} 檔符合條件：")
            st.dataframe(
                df_res.sort_values(by="量比(5/20)", ascending=False), 
                use_container_width=True
            )
        else:
            st.warning("掃描完成，目前市場無標的符合「量比 > 1.85 且 K > 80」的條件。")
    else:
        st.error("無法取得清單，請檢查連線環境。")
