import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="台股飆股進階掃描", layout="wide")

@st.cache_data(ttl=3600)
def get_all_tickers():
    # 這裡確保只抓取有效的 TW 股票代號
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=10)
            df = pd.read_html(resp.text)[0]
            df = df.iloc[1:, [0]]
            df.columns = ['代號名稱']
            df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
            all_tickers.extend([f"{t}.TW" for t in df['代號'].dropna().unique()])
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers):
    results_gain, results_high = [], []
    progress_bar = st.progress(0)
    
    # 為了避免 yfinance 限制，分批次處理
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        try:
            # 獲取資料
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True)
            
            for s in batch:
                # 處理 yfinance 可能回傳單一股票或多股票的不同結構
                df = data[s] if len(batch) > 1 else data
                if df.empty or len(df) < 125: continue
                
                # 計算指標
                curr_close = float(df['Close'].iloc[-1])
                vol_ratio = (df['Volume'].rolling(5).mean().iloc[-1]) / (df['Volume'].rolling(20).mean().iloc[-1])
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                three_day_gain = (curr_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                six_mo_high = df['Close'].rolling(120).max().iloc[-1]

                # 篩選條件
                if vol_ratio > 1.85 and k_val > 80:
                    if three_day_gain > 0.20:
                        results_gain.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "3日漲幅": f"{round(three_day_gain*100, 2)}%", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    if curr_close >= six_mo_high:
                        results_high.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
            
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            continue
            
    return pd.DataFrame(results_gain), pd.DataFrame(results_high)

# UI 介面
st.title("📊 台股飆股進階掃描器")
if st.button("啟動全面掃描"):
    with st.spinner('正在從市場下載並計算指標...'):
        all_tickers = get_all_tickers()
        df1, df2 = run_scanner(all_tickers)
        
    tab1, tab2 = st.tabs(["🚀 短線強勢 (3天漲幅 > 20%)", "📈 中線突破 (半年新高)"])
    
    with tab1:
        if not df1.empty: st.dataframe(df1, use_container_width=True)
        else: st.warning("未搜尋到符合 3 日漲幅 > 20% 的標的，建議檢查條件是否過嚴。")
            
    with tab2:
        if not df2.empty: st.dataframe(df2, use_container_width=True)
        else: st.warning("未搜尋到符合半年新高條件的標的。")
