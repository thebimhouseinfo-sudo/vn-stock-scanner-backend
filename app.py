import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging
import os

# Cấu hình logging để xem lỗi trên Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VN Stock Scanner API")

# Cấu hình CORS cực kỳ quan trọng để Frontend gọi được API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockResponse(BaseModel):
    ticker: str
    price: float
    change_pc: float
    volume_10d_avg: float
    market_cap: float
    pe: Optional[float]
    pb: Optional[float]
    roe: Optional[float]
    score: float
    recommendation: str

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "Backend is running successfully"}

@app.get("/api/scan", response_model=List[StockResponse])
def scan_market():
    # Mock data tạm thời để đảm bảo API không bị crash khi vnstock lỗi nguồn dữ liệu
    logger.info("Scan request received")
    try:
        mock_data = [
            {
                "ticker": "VNM", "price": 68000.0, "change_pc": 0.5,
                "volume_10d_avg": 2000000.0, "market_cap": 140000.0,
                "pe": 18.5, "pb": 2.1, "roe": 25.0, "score": 85.0, "recommendation": "BUY"
            },
            {
                "ticker": "SSI", "price": 35000.0, "change_pc": 2.1,
                "volume_10d_avg": 15000000.0, "market_cap": 50000.0,
                "pe": 15.2, "pb": 1.8, "roe": 12.0, "score": 70.0, "recommendation": "HOLD"
            },
            {
                "ticker": "HPG", "price": 28000.0, "change_pc": -1.2,
                "volume_10d_avg": 25000000.0, "market_cap": 160000.0,
                "pe": 12.0, "pb": 1.5, "roe": 10.0, "score": 65.0, "recommendation": "WATCH"
            }
        ]
        return mock_data
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    # Render yêu cầu port phải lấy từ biến môi trường
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
