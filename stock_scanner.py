import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
from streamlit_autorefresh import st_autorefresh
import datetime

# 1. 頁面設定
st.set_page_config(page_title="台股全市場飆股掃描器", layout="wide")

# 每 30 秒自動刷新
st_autorefresh(interval=30000, key="datarefresh")

# 2. 強健的股票代碼抓取 (確保抓到 1800+ 檔)
@st.cache_data(ttl=86400)
def get_all_stocks():
    codes = []
    # 分別抓取上市 (2) 與 上櫃 (4)
    for mode in ["2", "4"]:
        try:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            res = requests.get(url, timeout=10)
            df = pd.read_html(res.text)[0]
            # 整理資料：只保留代碼是 4 碼的普通股
            for item in df.iloc[:, 0]:
                match = re.match(r'^(\d{4})\s+', str(item))
                if match:
                    codes.append(f"{match.group(1)}.TW")
        except:
            continue
    return list(set(codes))

# 3. 掃描核心 (完全符合你的條件)
def scan_market(stock_list):
    results = []
    # 一次下載全市場數據 (速度最快)
    # 建議：如果伺服器跑不動，可改為 stock_list[:500] 測試
    data = yf.download(stock_list, period="1mo", interval="1d", group_by='ticker', threads=True)
    
    for s in stock_list:
        try:
            # 確保資料結構正確
            df = data[s] if len(data.columns.levels[0]) > 1 else data
            df = df.dropna()
            if len(df) < 20: continue

            # --- 你的條件 ---
            # 1. 量比 (5MA/20MA > 1.85)
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = vol5 / vol20

            # 2. 漲幅條件
            close_now = df['Close'].iloc[-1]
            close_3 = df['Close'].iloc[-4]
            return3 = (close_now - close_3) / close_3
            
            df['ret'] = df['Close'].pct_change()
            limit_up_hits = (df['ret'] >= 0.098).rolling(3).sum().iloc[-1]
            
            # 3. KD(9,3,3) > 80
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = stoch.stoch().iloc[-1]

            # 判斷觸發
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_hits >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(float(close_now), 2),
                    "量比": round(float(vol_ratio), 2),
                    "3日漲幅%": round(float(return3 * 100), 2),
                    "K值": round(float(k_val), 2)
                })
        except:
            continue
    return pd.DataFrame(results)

# 4. 介面呈現
st.title("🔥 全台股噴發掃描器")
st.write(f"最後更新：{datetime.datetime.now().strftime('%H:%M:%S')} (每30秒自動掃描)")

all_stocks = get_all_stocks()
st.info(f"掃描範圍：全市場 {len(all_stocks)} 檔股票")

with st.spinner("正在掃描市場中，請稍候..."):
    df_result = scan_market(all_stocks)

if not df_result.empty:
    st.success(f"成功找到 {len(df_result)} 檔符合標的")
    st.dataframe(df_result.sort_values("量比", ascending=False), use_container_width=True)
else:
    st.warning("目前沒有股票符合所有條件。")
