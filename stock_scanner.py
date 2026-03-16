import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
from streamlit_autorefresh import st_autorefresh
import datetime

# 頁面設定
st.set_page_config(page_title="台股飆股掃描", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 每 60 秒更新一次，避免過度請求

# 1. 取得全台股清單
@st.cache_data(ttl=3600)
def get_all_stocks():
    codes = []
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

# 2. 分批掃描核心 (解決 ValueError 的關鍵)
def scan_in_batches(stock_list):
    results = []
    batch_size = 30  # 每次處理 30 檔，穩健度最高
    
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i : i + batch_size]
        try:
            # 分批下載
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            # 若 batch 只有一檔，格式會不同，需統一轉為 DataFrame 字典
            if len(batch) == 1:
                data_dict = {batch[0]: data}
            else:
                data_dict = {s: data[s] for s in batch if s in data.columns.levels[0]}

            for s in batch:
                if s not in data_dict or data_dict[s].empty or len(data_dict[s]) < 20:
                    continue
                
                df = data_dict[s].dropna()

                # --- 你的條件判斷 ---
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                vol_ratio = vol5 / vol20

                close_now = df['Close'].iloc[-1]
                close_3 = df['Close'].iloc[-4]
                return3 = (close_now - close_3) / close_3
                
                df['ret'] = df['Close'].pct_change()
                limit_up_hits = (df['ret'] >= 0.098).rolling(3).sum().iloc[-1]
                
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = stoch.stoch().iloc[-1]

                if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_hits >= 2) and k_val > 80:
                    results.append({
                        "股票": s.replace(".TW", ""),
                        "價格": round(float(close_now), 2),
                        "量比": round(float(vol_ratio), 2),
                        "3日漲幅%": round(float(return3 * 100), 2),
                        "K值": round(float(k_val), 2)
                    })
        except Exception:
            continue
    return pd.DataFrame(results)

# 3. UI 呈現
st.title("🔥 全台股噴發掃描器")
st.write(f"最後更新：{datetime.datetime.now().strftime('%H:%M:%S')}")

all_stocks = get_all_stocks()
st.info(f"掃描範圍：全市場 {len(all_stocks)} 檔股票 (分批處理中...)")

with st.spinner("正在執行掃描，請稍候..."):
    df_result = scan_in_batches(all_stocks)

if not df_result.empty:
    st.success(f"找到 {len(df_result)} 檔符合條件標的")
    st.dataframe(df_result.sort_values("量比", ascending=False), use_container_width=True)
else:
    st.warning("目前沒有符合所有條件的股票。")
