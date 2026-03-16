import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="診斷模式", layout="wide")

st.title("🛠️ 資料診斷模式")
ticker = st.text_input("輸入股票代碼測試 (如 2330.TW)", "2330.TW")

if st.button("開始診斷測試"):
    try:
        # 下載資料
        df = yf.download(ticker, period="2mo", interval="1d", progress=False)
        
        if df.empty:
            st.error("錯誤：無法下載到資料，請檢查代碼格式或網路狀況。")
        else:
            # 顯示原始數據前幾行，檢查欄位名稱是否正確
            st.write("### 原始資料結構 (前5筆):")
            st.write(df.head())
            
            # 檢查是否有成交量
            if 'Volume' not in df.columns:
                st.error("錯誤：資料中找不到 'Volume' (成交量) 欄位！")
            else:
                # 計算看看
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                st.write(f"### 計算結果:")
                st.write(f"- 5日均量: {vol5}")
                st.write(f"- 20日均量: {vol20}")
                st.write(f"- 量比: {vol5/vol20 if vol20 != 0 else '除以0'}")
                st.write(f"- 最新收盤價: {df['Close'].iloc[-1]}")
                
                st.success("診斷完成：如果以上數值都有出來，代表數據源沒問題，是你篩選條件的數值範圍太極端了。")
    except Exception as e:
        st.error(f"發生系統錯誤: {e}")
