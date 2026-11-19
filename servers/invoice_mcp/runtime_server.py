import os
import sys
import uuid
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI()
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class InvoiceItem(BaseModel):
    name: str
    amount: float
    quantity: int


class InvoiceRequest(BaseModel):
    customer_name: str
    items: List[InvoiceItem]


@app.post("/generate_invoice")
async def generate_invoice(request: InvoiceRequest):
    if request.customer_name.strip().startswith("/"):
        try:
            safe_path(request.customer_name.strip())
        except PathNotAllowed as e:
            raise HTTPException(status_code=403, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    try:
        filename = f"invoice_{uuid.uuid4().hex}.pdf"
        filepath = OUTPUTS_DIR / filename

        c = canvas.Canvas(str(filepath), pagesize=letter)
        c.drawString(100, 750, f"Invoice for: {request.customer_name}")
        y = 700
        total = 0
        for item in request.items:
            line_total = item.amount * item.quantity
            total += line_total
            c.drawString(100, y, f"{item.name} x {item.quantity}: ${line_total:.2f}")
            y -= 20
        c.drawString(100, y - 20, f"Total: ${total:.2f}")
        c.save()

        return {"filepath": str(filepath.resolve())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8064)
