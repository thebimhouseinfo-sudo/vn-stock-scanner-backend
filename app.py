import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import numpy as np
import pandas as pd
from vnstock import *
from datetime import datetime
import os
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VN Stock Scanner API - Professional Version")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# MODELS
# ========================================

class ScoringResult(BaseModel):
    ticker: str
    sector: str
    micro_score: float
    quality_score: float
    growth_score: float
    value_score: float
    mispricing_score: float
    momentum_score: float
    final_score: float
    recommendation: str
    price: float
    pe: float

# ========================================
# SCORING LOGIC HELPERS
# ========================================

def calculate_percentile(values: pd.Series, target: float) -> float:
    if values.empty: return 50
    sorted_vals = values.sort_values()
    count = (sorted_vals <= target).sum()
    return (count / len(sorted_vals)) * 100

# ========================================
# DATA FETCHING & PROCESSING
# ========================================

@app.get("/api/scan", response_model=List[ScoringResult])
def scan_market():
    try:
        logger.info("Fetching listing companies...")
        # 1. Lấy danh sách công ty (Giới hạn 30 mã để tránh Render timeout ở bản Free)
        df_listing = listing_companies()
        tickers = df_listing['ticker'].head(30).tolist()
        
        results = []
        
        # 2. Lấy Financial Ratios cho toàn bộ danh sách (Batch processing nếu API hỗ trợ)
        # Ở đây ta loop qua từng mã để tính điểm theo logic 5 lớp của bạn
        for ticker in tickers:
            try:
                # Lấy chỉ số tài chính
                df_ratio = financial_ratio(ticker, 'yearly').iloc[0] # Lấy năm gần nhất
                
                # Giả lập dữ liệu giá và biến động (vnstock lấy giá qua hàm khác)
                # Để đảm bảo code chạy, ta dùng các chỉ số cơ bản từ df_ratio
                roe = df_ratio.get('roe', 0) * 100
                pe = df_ratio.get('priceToEarning', 15)
                pb = df_ratio.get('priceToBook', 1)
                eps_growth = df_ratio.get('epsChange', 0) * 100
                revenue_growth = df_ratio.get('revenueChange', 0) * 100
                
                # Logic Chấm điểm 5 lớp rút gọn
                # Layer 1: Quality (ROE)
                q_score = min(roe / 2, 10) 
                # Layer 2: Growth
                g_score = min(max(eps_growth / 5, 0), 10)
                # Layer 3: Value (P/E thấp thì điểm cao)
                v_score = max(10 - (pe / 3), 0)
                
                micro_score = (q_score * 0.4 + g_score * 0.3 + v_score * 0.3)
                
                # Layer 4: Mispricing (Giả lập dựa trên P/B thấp)
                mispricing = 10 if pb < 1 else 5 if pb < 2 else 0
                
                # Layer 5: Momentum (Giả lập mặc định)
                momentum = 5.0
                
                final_score = (micro_score * 1.5) + mispricing + momentum
                
                # Phân loại khuyến nghị
                if final_score > 22: rec = "🟢 STRONG BUY"
                elif final_score > 18: rec = "🟡 BUY"
                elif final_score > 14: rec = "⚪ HOLD"
                else: rec = "🔴 AVOID"

                results.append(ScoringResult(
                    ticker=ticker,
                    sector="General", # Cần mapping sector từ listing nếu muốn chi tiết
                    micro_score=round(micro_score, 2),
                    quality_score=round(q_score, 2),
                    growth_score=round(g_score, 2),
                    value_score=round(v_score, 2),
                    mispricing_score=round(mispricing, 2),
                    momentum_score=round(momentum, 2),
                    final_score=round(final_score, 2),
                    recommendation=rec,
                    price=0.0, # Cần gọi hàm price_board() để lấy giá real-time
                    pe=round(pe, 2)
                ))
            except Exception as e:
                logger.error(f"Skip {ticker} due to error: {e}")
                continue

        # Sắp xếp theo điểm cao nhất
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results

    except Exception as e:
        logger.error(f"General Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
