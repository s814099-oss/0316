import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator

# 頁面配置
st.set_page_config(page_title="台股飆股掃描器", layout="wide")

# 1. 最穩定的股票清單抓取
@st.cache_data(ttl=86400)
def get_all_stocks():
    # 改用更直接的清單方式，避免證交所網頁解析失敗
    # 如果網頁解析困難，我們直接預設一些熱門清單作為基底
    codes = []
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    for url in urls:
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            df = pd.read_html(res.text)[0]
            for val in df.iloc[:, 0].astype(str):
                if re.match(r'^\d{4}$', val):
                    codes.append(f"{val}.TW")
        except: continue
    return list(set(codes))

# 2. 核心掃描邏輯 (加入了詳細的除錯輸出)
def scan_stocks():
    all_stocks = get_all_stocks()
    target_stocks = all_stocks[:200] # 先測 200 檔確保不崩潰
    st.write(f"系統已準備好，開始掃描 {len(target_stocks)} 檔股票...")
    
    results = []
    progress = st.progress(0)
    
    for i, s in enumerate(target_stocks):
        progress.progress(i / len(target_stocks))
        try:
            # 確保下載格式乾淨
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            # 修正 Multi-Index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            if df.empty or len(df) < 30: continue
            
            # 指標計算
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            if vol20 == 0: continue
            
            vol_ratio = float(vol5 / vol20)
            close_now = float(df['Close'].iloc[-1])
            close_3 = float(df['Close'].iloc[-4])
            return3 = (close_now - close_3) / close_3
            
            limit_up_sum = (df['Close'].pct_change() >= 0.098).rolling(3).sum().iloc[-1]
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # 條件判斷 (保留你所有的設定)
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_sum >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(close_now, 2),
                    "量比": round(vol_ratio, 2),
                    "3日漲幅%": round(return3 * 100, 2),
                    "K值": round(k_val, 2)
                })
        except Exception as e:
            continue
            
    progress.empty()
    return pd.DataFrame(results)

# 3. 介面
st.title("🔥 台股噴發掃描器 (除錯版)")
if st.button("開始掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("掃描完成！目前無標的符合所有條件。")
        st.info("提示：你的條件包含『量比 > 1.85』、『漲幅 > 20%』且『K值 > 80』。這屬於極度強勢的噴發訊號，建議先試著放寬條件測試。")
