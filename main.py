from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path
import os

app = FastAPI(title="QR Receipt Scanner")

# Определяем путь к templates относительно этого файла
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

# Если нет templates рядом, проверяем в корне проекта
if not TEMPLATE_DIR.exists():
    TEMPLATE_DIR = Path("/var/task/templates")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Временное хранилище (для Vercel)
RECEIPTS_FILE = Path("/tmp/receipts.json")

def load_receipts():
    try:
        if RECEIPTS_FILE.exists():
            with open(RECEIPTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading receipts: {e}")
    return []

def save_receipt(receipt_data):
    try:
        receipts = load_receipts()
        receipt_data['scanned_at'] = datetime.now().isoformat()
        receipt_data['id'] = len(receipts) + 1
        receipts.insert(0, receipt_data)
        
        RECEIPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(RECEIPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(receipts, f, ensure_ascii=False, indent=2)
        
        return receipt_data
    except Exception as e:
        print(f"Error saving receipt: {e}")
        return receipt_data

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        receipts = load_receipts()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "receipts": receipts,
            "receipts_json": json.dumps(receipts, ensure_ascii=False)
        })
    except Exception as e:
        return HTMLResponse(
            f"<h1>Error</h1><p>{str(e)}</p><p>Template dir: {TEMPLATE_DIR}</p><p>Exists: {TEMPLATE_DIR.exists()}</p>",
            status_code=500
        )

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "template_dir": str(TEMPLATE_DIR),
        "exists": TEMPLATE_DIR.exists(),
        "base_dir": str(BASE_DIR)
    }

@app.get("/api/receipts")
async def get_receipts():
    return JSONResponse({"receipts": load_receipts()})

@app.delete("/api/receipts/{receipt_id}")
async def delete_receipt(receipt_id: int):
    try:
        receipts = load_receipts()
        receipts = [r for r in receipts if r.get('id') != receipt_id]
        
        with open(RECEIPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(receipts, f, ensure_ascii=False, indent=2)
        
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/fetch-receipt")
async def fetch_receipt(url: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            
            company = "Неизвестно"
            h3_bold = soup.find('h3', style=lambda x: x and 'font-weight' in x and 'bold' in x)
            if h3_bold:
                company = h3_bold.get_text(strip=True)
            
            receipt_num = "N/A"
            first_b = soup.find('td').find('b') if soup.find('td') else None
            if first_b:
                receipt_num = first_b.get_text(strip=True)
            
            date_time = "N/A"
            for italic in soup.find_all('i'):
                text = italic.get_text(strip=True)
                if '.' in text and any(c.isdigit() for c in text):
                    date_time = text
                    break
            
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
            
            total = "0"
            for td in soup.find_all('td'):
                if 'Jami to`lov' in td.get_text():
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        total = next_td.get_text(strip=True)
                        break
            
            receipt_data = {
                "url": url,
                "companyName": company,
                "receiptNumber": receipt_num,
                "dateTime": date_time,
                "products": products,
                "total": total
            }
            
            saved = save_receipt(receipt_data)
            
            return JSONResponse({
                "success": True,
                "data": saved
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)