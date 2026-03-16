import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股全市場掃描器", layout="wide")

# 1. 自動抓取證交所最新上市櫃代碼清單
@st.cache_data(ttl=86400)
def get_all_stock_tickers():
    # 這是證交所提供的 CSV 下載連結
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        df = pd.read_html(url)[0]
        # 清理資料：只留下代號為 4 碼數字的股票
        df = df.iloc[1:, :2]
        df.columns = ['代號名稱', 'ISIN']
        # 分割代號與名稱
        df['代號'] = df['代號名稱'].str.split(expand=True)[0]
        # 過濾掉非 4 碼數字的代號 (例如權證或債券)
        tickers = df[df['代號'].str.match(r'^\d{4}$')]['代號'] + ".TW"
        return tickers.tolist()
    except Exception as e:
        st.error(f"無法獲取股票清單: {e}")
        return []

# 2. 掃描核心
def scan_stocks(tickers):
    results = []
    st.write(f"系統已載入 {len(tickers)} 檔股票，開始進行深度掃描...")
    progress_bar = st.progress(0)
    
    # 為了避免被 Yahoo 封鎖，我們使用隨機延遲並分批處理
    for i, s in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            # 隨機延遲 (0.2 - 0.5 秒) 以模擬真人行為
            time.sleep(random.uniform(0.2, 0.5))
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 20: continue
            
            # 計算指標
            price = float(df['Close'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            if vol20 == 0: continue
            
            vol_ratio = vol5 / vol20
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'])
            k_val = float(stoch.stoch().iloc[-1])
            
            if vol_ratio > 1.5 and k_val > 70:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(price, 2),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except: continue
            
    return pd.DataFrame(results)

# 3. 介面呈現
st.title("📊 台股全市場飆股掃描器")
if st.button("啟動全市場掃描"):
    all_tickers = get_all_stock_tickers()
    if all_tickers:
        df_res = scan_stocks(all_tickers)
        if not df_res.empty:
            st.dataframe(df_res.sort_values(by="量比", ascending=False), width=None)
        else:
            st.warning("掃描完成，無標的符合設定條件。")
    else:
        st.error("無法取得股票列表，請檢查網路。")
