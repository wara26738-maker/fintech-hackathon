# src/tools/investment.py
import akshare as ak
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

def _get_realtime_price(symbol: str) -> float:
    """ดึงราคาเรียลไทม์ผ่าน AKShare (ใช้วิธีดึงกระดานรวมเพื่อความชัวร์)"""
    try:
        # ดึงข้อมูลทั้งกระดาน (เร็วกว่าและเสถียรกว่าการดึงรายตัว)
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == symbol]
        if not row.empty:
            return float(row.iloc[0]['最新价'])
    except Exception as e:
        print(f"AKShare realtime error for {symbol}: {e}")
    return 0.0

def _get_historical_trend(symbol: str, market_prefix: str = "sh") -> str:
    """ดึงข้อมูลย้อนหลัง 30 วันผ่าน BaoStock เพื่อดูแนวโน้ม"""
    try:
        lg = bs.login()
        if lg.error_code != '0':
            return "Unknown Trend"
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        rs = bs.query_history_k_data_plus(
            f"{market_prefix}.{symbol}", 
            "date,close", 
            start_date=start_date, 
            end_date=end_date, 
            frequency="d", 
            adjustflag="3"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if len(data_list) < 2:
            return "Insufficient Data"
            
        df = pd.DataFrame(data_list, columns=rs.fields)
        df['close'] = pd.to_numeric(df['close'])
        
        first_price = df['close'].iloc[0]
        last_price = df['close'].iloc[-1]
        change_pct = ((last_price - first_price) / first_price) * 100
        
        if change_pct > 5:
            return f"Strong Uptrend (+{change_pct:.1f}% / 30d)"
        elif change_pct > 0:
            return f"Mild Uptrend (+{change_pct:.1f}% / 30d)"
        elif change_pct > -5:
            return f"Mild Downtrend ({change_pct:.1f}% / 30d)"
        else:
            return f"Strong Downtrend ({change_pct:.1f}% / 30d)"
            
    except Exception as e:
        print(f"BaoStock historical error for {symbol}: {e}")
        return "Error Fetching Trend"

def analyze_real_investment(budget: float, risk: str, goal: str) -> Dict[str, Any]:
    if risk == "Low":
        universe = [
            {"symbol": "600519", "name": "Kweichow Moutai", "market": "sh", "reason": "High dividend, strong brand moat."},
            {"symbol": "601398", "name": "ICBC", "market": "sh", "reason": "State-owned bank, stable dividend."}
        ]
        summary = "Conservative portfolio focusing on stable dividend yields."
    elif risk == "High":
        universe = [
            {"symbol": "300750", "name": "CATL", "market": "sz", "reason": "EV battery leader, high growth potential."},
            {"symbol": "002594", "name": "BYD", "market": "sz", "reason": "EV maker, strong sales momentum."}
        ]
        summary = "Aggressive portfolio targeting high-growth tech and EV sectors."
    else:
        universe = [
            {"symbol": "600036", "name": "China Merchants Bank", "market": "sh", "reason": "Retail banking leader, solid fundamentals."},
            {"symbol": "000858", "name": "Wuliangye", "market": "sz", "reason": "Premium liquor, consistent earnings."}
        ]
        summary = "Balanced portfolio blending stability with growth potential."

    stocks = []
    for stock in universe:
        price = _get_realtime_price(stock["symbol"])
        trend = _get_historical_trend(stock["symbol"], stock["market"])
        
        # Fallback price หาก API ล่ม
        if price <= 0:
            price = 100.0 
            
        stocks.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "price": price,
            "trend": trend,
            "reason": stock["reason"],
            "alloc_pct": 100 / len(universe)
        })

    for s in stocks:
        alloc_amount = budget * (s["alloc_pct"] / 100)
        s["alloc_amount"] = alloc_amount
        s["shares"] = round(alloc_amount / s["price"], 2) if s["price"] > 0 else 0

    return {
        "status": "success",
        "data": {
            "summary": summary,
            "stocks": stocks,
            "budget": budget,
            "risk": risk,
            "goal": goal
        }
    }