from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path
import os

app = FastAPI()

# Путь к шаблонам
template_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_path))

# Временное хранилище (данные пропадут при рестарте)
receipts_storage = []

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "receipts": receipts_storage,
        "receipts_json": json.dumps(receipts_storage, ensure_ascii=False)
    })

@app.get("/api/receipts")
async def get_receipts():
    return {"receipts": receipts_storage}

@app.delete("/api/receipts/{receipt_id}")
async def delete_receipt(receipt_id: int):
    global receipts_storage
    receipts_storage = [r for r in receipts_storage if r.get('id') != receipt_id]
    return {"success": True}

@app.get("/api/fetch-receipt")
async def fetch_receipt(url: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Парсинг компании
        company = "Неизвестно"
        h3_bold = soup.find('h3', style=lambda x: x and 'font-weight' in x and 'bold' in x)
        if h3_bold:
            company = h3_bold.get_text(strip=True)
        
        # Номер чека
        receipt_num = "N/A"
        first_b = soup.find('td')
        if first_b:
            first_b = first_b.find('b')
            if first_b:
                receipt_num = first_b.get_text(strip=True)
        
        # Дата
        date_time = "N/A"
        for italic in soup.find_all('i'):
            text = italic.get_text(strip=True)
            if '.' in text and any(c.isdigit() for c in text):
                date_time = text
                break
        
        # Товары
        products = []
        product_rows = soup.find_all('tr', class_='products-row')
        
        for row in product_rows:
            name_td = row.find('td', recursive=False)
            qty_td = row.find('td', align='center')
            price_td = row.find('td', class_='price-sum')
            
            if name_td and qty_td and price_td:
                products.append({
                    'name': name_td.get_text(strip=True),
                    'quantity': qty_td.get_text(strip=True),
                    'price': price_td.get_text(strip=True)
                })
        
        # Итого
        total = "0"
        for td in soup.find_all('td'):
            if 'Jami to`lov' in td.get_text():
                next_td = td.find_next_sibling('td')
                if next_td:
                    total = next_td.get_text(strip=True)
                    break
        
        receipt_data = {
            "id": len(receipts_storage) + 1,
            "url": url,
            "companyName": company,
            "receiptNumber": receipt_num,
            "dateTime": date_time,
            "products": products,
            "total": total,
            "scanned_at": datetime.now().isoformat()
        }
        
        receipts_storage.insert(0, receipt_data)
        
        return {"success": True, "data": receipt_data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "receipts_count": len(receipts_storage),
        "template_path": str(template_path),
        "exists": template_path.exists()
    }

# Для Vercel
app = app