import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
import datetime

# 設定手機觀看友善頁面
st.set_page_config(page_title="台股飆股掃描器", layout="wide")

# 1. 取得全台股普通股代碼
@st.cache_data(ttl=86400)
def get_all_stocks():
    codes = []
    # 分別抓取上市 (2) 與 上櫃 (4)
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

# 2. 核心掃描邏輯 (回溯過去 20 天)
def scan_stocks(stock_list):
    results = []
    batch_size = 50 # 批次下載以確保穩定
    progress = st.progress(0)
    
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i : i + batch_size]
        progress.progress(i / len(stock_list))
        
        try:
            # 下載 2 個月數據以計算 20 日均量
            data = yf.download(batch, period="2mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for s in batch:
                ticker_df = data[s] if len(batch) > 1 else data
                if ticker_df.empty or len(ticker_df) < 30: continue
                
                df = ticker_df.dropna().copy()
                
                # --- 技術指標計算 ---
                # KD(9,3,3)
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                df['K'] = stoch.stoch()
                
                # 量比 (5日均量 / 20日均量)
                df['Vol5'] = df['Volume'].rolling(5).mean()
                df['Vol20'] = df['Volume'].rolling(20).mean()
                
                # 漲停判定 (近三日是否有兩次漲停)
                df['ret'] = df['Close'].pct_change()
                df['limit_up'] = (df['ret'] >= 0.098)
                df['limit_sum'] = df['limit_up'].rolling(3).sum()
                
                # 計算三日漲幅
                df['return3'] = df['Close'].pct_change(periods=3)

                # --- 條件篩選 (回溯過去 20 天) ---
                for day in range(20):
                    idx = -(day + 1)
                    if idx < -len(df): break
                    
                    # 你的原始三大條件：
                    # 1. 量比 > 1.85
                    # 2. 三日漲幅 > 20% OR 三天兩根漲停
                    # 3. K值 > 80
                    cond_vol = (df['Vol5'].iloc[idx] / df['Vol20'].iloc[idx]) > 1.85
                    cond_price = (df['return3'].iloc[idx] > 0.20 or df['limit_sum'].iloc[idx] >= 2)
                    cond_k = df['K'].iloc[idx] > 80
                    
                    if cond_vol and cond_price and cond_k:
                        results.append({
                            "股票": s.replace(".TW", ""),
                            "發生時間": f"{day} 天前",
                            "價格": round(float(df['Close'].iloc[idx]), 2),
                            "量比": round(float(df['Vol5'].iloc[idx] / df['Vol20'].iloc[idx]), 2),
                            "K值": round(float(df['K'].iloc[idx]), 2)
                        })
                        break # 符合條件後跳出該股票的檢查
        except: continue
        
    progress.empty()
    return pd.DataFrame(results)

# 3. 介面
st.title("🔥 全台股噴發掃描器")
if st.button("開始執行全市場掃描"):
    all_stocks = get_all_stocks()
    df_res = scan_stocks(all_stocks)
    if not df_res.empty:
        st.success(f"找到 {len(df_res)} 檔標的")
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("目前市場無標的符合條件。")
