import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="台股飆股與突破掃描", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
    df = pd.read_html(resp.text)[0]
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_full_market(all_tickers):
    results_gain = [] # 飆股策略結果
    results_high = [] # 半年新高結果
    batch_size = 30
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        try:
            # 下載半年資料以計算 3 天漲幅與半年新高
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 125: continue
                
                curr_close = float(df['Close'].iloc[-1])
                # 量比: 5日均量 / 20日均量
                vol_ratio = (df['Volume'].rolling(5).mean().iloc[-1]) / (df['Volume'].rolling(20).mean().iloc[-1])
                # K 值
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9)
                k = float(stoch.stoch().iloc[-1])
                
                # 策略 1: 3天漲幅 > 20% 且 量比 > 1.85 且 K > 80
                three_day_gain = (curr_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                if vol_ratio > 1.85 and k > 80 and three_day_gain > 0.20:
                    results_gain.append({"代號": ticker.replace(".TW", ""), "現價": round(curr_close, 2), "漲幅": f"{round(three_day_gain*100, 1)}%", "量比": round(float(vol_ratio), 2)})
                
                # 策略 2: 半年新高
                six_mo_high = df['Close'].rolling(120).max().iloc[-1]
                if curr_close >= six_mo_high and vol_ratio > 1.5:
                    results_high.append({"代號": ticker.replace(".TW", ""), "現價": round(curr_close, 2), "量比": round(float(vol_ratio), 2)})
            
            time.sleep(random.uniform(5, 8))
        except Exception:
            continue
            
    return pd.DataFrame(results_gain), pd.DataFrame(results_high)

# --- UI 渲染 ---
st.title("📊 飆股策略全市場掃描")
if st.button("啟動掃描 (3天強勢飆股 & 半年突破)"):
    with st.spinner("正在執行複雜運算與全市場下載..."):
        all_tickers = get_all_tickers()
        df1, df2 = scan_full_market(all_tickers)
        
        tab1, tab2 = st.tabs(["🚀 短線強勢 (3天漲幅>20%)", "📈 中線突破 (半年新高)"])
        
        with tab1:
            if not df1.empty: st.dataframe(df1, use_container_width=True)
            else: st.info("無符合短線飆漲條件的標的")
            
        with tab2:
            if not df2.empty: st.dataframe(df2, use_container_width=True)
            else: st.info("無符合半年突破條件的標的")
