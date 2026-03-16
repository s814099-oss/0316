import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
import datetime

# 頁面配置
st.set_page_config(page_title="台股飆股掃描器", layout="wide")

# 1. 取得全台股清單 (包含上市櫃)
@st.cache_data(ttl=86400)
def get_all_stocks():
    codes = []
    # 抓取證交所與櫃買清單
    for mode in ["2", "4"]:
        try:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            res = requests.get(url, timeout=10)
            df = pd.read_html(res.text)[0]
            for item in df.iloc[:, 0]:
                match = re.match(r'^(\d{4})\s+', str(item))
                if match:
                    codes.append(f"{match.group(1)}.TW")
        except: continue
    return list(set(codes))

# 2. 核心掃描條件 (完全依照你的設定)
def run_scanner(stock_list):
    results = []
    batch_size = 50 # 分批處理避免崩潰
    progress = st.progress(0)
    
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i : i + batch_size]
        progress.progress(i / len(stock_list))
        
        try:
            # 下載數據
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for s in batch:
                # 確保該代碼有正確下載到數據
                ticker_df = data[s] if len(batch) > 1 else data
                if ticker_df.empty or len(ticker_df) < 20: continue
                
                df = ticker_df.dropna()
                
                # --- 你的原始條件 ---
                # 1. 量比 (5日均量 / 20日均量 > 1.85)
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                vol_ratio = vol5 / vol20
                
                # 2. 三日漲幅 > 20% 或 三天內兩根漲停
                close_now = df['Close'].iloc[-1]
                close_3 = df['Close'].iloc[-4]
                return3 = (close_now - close_3) / close_3
                
                df['ret'] = df['Close'].pct_change()
                limit_up_hits = (df['ret'] >= 0.098).rolling(3).sum().iloc[-1]
                
                # 3. K值 > 80 (KD 9,3,3)
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = stoch.stoch().iloc[-1]
                
                # 最終判斷
                if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_hits >= 2) and k_val > 80:
                    results.append({
                        "股票": s.replace(".TW", ""),
                        "價格": round(float(close_now), 2),
                        "量比": round(float(vol_ratio), 2),
                        "3日漲幅%": round(float(return3 * 100), 2),
                        "K值": round(float(k_val), 2)
                    })
        except: continue
        
    progress.empty()
    return pd.DataFrame(results)

# 3. UI 介面
st.title("🔥 全台股噴發掃描器")
st.write(f"系統時間: {datetime.datetime.now().strftime('%H:%M:%S')}")

if st.button("開始執行全市場掃描"):
    all_stocks = get_all_stocks()
    st.info(f"正在掃描全市場 {len(all_stocks)} 檔股票...")
    
    df_res = run_scanner(all_stocks)
    
    if not df_res.empty:
        st.success(f"找到 {len(df_res)} 檔符合條件標的")
        st.dataframe(df_res.sort_values("量比", ascending=False), use_container_width=True)
    else:
        st.warning("目前全市場沒有標的同時滿足你的三大條件。")

st.caption("註：你的條件非常精準且嚴格，掃不到股票屬於正常現象，代表目前市場沒有處於極端噴發狀態。")
