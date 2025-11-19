import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Transaction

app = FastAPI(title="Money Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Money Manager Backend is running"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Request models
class CreateTransactionRequest(BaseModel):
    amount: float
    type: str
    category: str
    note: Optional[str] = None
    date: Optional[datetime] = None


# Endpoints for transactions
@app.post("/api/transactions")
def create_transaction(payload: CreateTransactionRequest):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if payload.type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Type must be 'income' or 'expense'")

    # Build document
    data = {
        "amount": float(payload.amount),
        "type": payload.type,
        "category": payload.category,
        "note": payload.note,
        "date": payload.date or datetime.now(timezone.utc),
    }
    doc_id = create_document("transaction", data)
    return {"id": doc_id, **data}


@app.get("/api/transactions")
def list_transactions(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=1970, le=3000),
):
    # Filter by month/year if provided
    filter_dict = {}
    if month and year:
        # Build date range for the month
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        filter_dict = {"date": {"$gte": start, "$lt": end}}

    docs = get_documents("transaction", filter_dict)
    # Convert ObjectId and datetime for JSON
    result = []
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
        if isinstance(d.get("date"), datetime):
            d["date"] = d["date"].isoformat()
        result.append(d)
    return {"items": result}


@app.get("/api/summary/month")
def monthly_summary(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=1970, le=3000),
):
    # Default to current month/year if not provided
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    filter_dict = {"date": {"$gte": start, "$lt": end}}
    docs = get_documents("transaction", filter_dict)

    total_income = 0.0
    total_expense = 0.0
    for d in docs:
        amt = float(d.get("amount", 0))
        if d.get("type") == "income":
            total_income += amt
        elif d.get("type") == "expense":
            total_expense += amt

    balance = total_income - total_expense

    return {
        "month": month,
        "year": year,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(balance, 2),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
