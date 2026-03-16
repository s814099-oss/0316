import streamlit as st
import pandas as pd
import yfinance as yf
import urllib3

# 關閉不安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.title("📊 台股診斷測試器")

# 1. 直接定義一檔測試股票
test_ticker = "2330.TW" 

if st.button("點擊測試下載資料"):
    st.write(f"正在下載 {test_ticker}...")
    try:
        # 使用最穩定的單檔下載方式
        stock = yf.Ticker(test_ticker)
        df = stock.history(period="1mo")
        
        if not df.empty:
            st.success("下載成功！")
            st.write(df.tail())
            
            # 檢查成交量單位
            vol = float(df['Volume'].iloc[-1])
            st.write(f"今日成交量 (股): {vol:,.0f}")
            
            if vol > 5000:
                st.write("符合成交量大於 5000 股的條件")
            else:
                st.write("成交量小於 5000 股")
        else:
            st.error("下載到的資料為空")
            
    except Exception as e:
        st.error(f"發生錯誤: {e}")
