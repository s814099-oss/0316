import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from datetime import datetime, timedelta

ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="台股飆股掃描器", layout="wide")

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
    res_20pct = []
    res_high = []
    total_count = len(tickers)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for i, batch in enumerate(batches):
        # 計算剩餘時間
        elapsed = time.time() - start_time
        avg_time = elapsed / (i + 1)
        eta_sec = (len(batches) - (i + 1)) * avg_time
        eta_str = str(timedelta(seconds=int(eta_sec)))
        
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"已處理: {min((i+1)*batch_size, total_count)}/{total_count} 檔 | 預計剩餘: {eta_str}")
        
        try:
            time.sleep(random.uniform(1.0, 1.5))
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=True)
            
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 120: continue 
                
                if float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
                
                cur_close = float(df['Close'].iloc[-1])
                
                # 策略 1: 3天漲幅 > 20% 或 近期出現漲停板 (簡單判斷)
                # 這裡定義：最近 3 天內漲幅 > 20%
                three_day_gain = (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                if three_day_gain >= 0.20:
                    res_20pct.append({"代號": s.replace(".TW", ""), "現價": cur_close, "漲幅": f"{three_day_gain:.2%}"})
                
                # 策略 2: 創半年新高 (收盤價 > 過去 120 天最高價)
                if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                    res_high.append({"代號": s.replace(".TW", ""), "現價": cur_close})
                    
        except: continue
    
    return pd.DataFrame(res_20pct), pd.DataFrame(res_high)

st.title("🔥 台股雙策略掃描器")
st.sidebar.subheader("參數設定")
min_vol = st.sidebar.number_input("最低成交量 (張)", value=500)

if st.button("開始執行掃描"):
    tickers = get_all_tickers()
    df_20, df_high = run_scanner(tickers, min_vol)
    
    tab1, tab2 = st.tabs(["🚀 短線爆發 (3天漲20% / 漲停)", "📈 半年新高趨勢"])
    with tab1:
        st.write(f"共找到 {len(df_20)} 檔")
        st.dataframe(df_20, use_container_width=True)
    with tab2:
        st.write(f"共找到 {len(df_high)} 檔")
        st.dataframe(df_high, use_container_width=True)
