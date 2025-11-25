from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path
import re
import os

app = FastAPI()

template_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_path))

receipts_storage = []
category_cache = {}

CATEGORIES = {
    "🍬 Сладости": [],
    "🥤 Напитки": [],
    "🍞 Хлеб и выпечка": [],
    "🥛 Молочные продукты": [],
    "🥩 Мясо и рыба": [],
    "🥗 Овощи и фрукты": [],
    "🍝 Крупы и макароны": [],
    "💊 Медицина и гигиена": [],
    "🧹 Бытовая химия": [],
    "🎁 Другое": []
}

def categorize_simple(product_name):
    name_lower = product_name.lower()
    
    if any(w in name_lower for w in ['печенье', 'шоколад', 'конфет', 'торт', 'пирожн', 'вафл', 'браун', 'pechenye', 'shokolad', 'brauni', 'cushion']):
        return "🍬 Сладости"
    
    if any(w in name_lower for w in ['сок', 'вод', 'чай', 'кофе', 'лимонад', 'cola', 'fanta', 'sprite', 'ichimlik', 'dyushes', 'pet']):
        return "🥤 Напитки"
    
    if any(w in name_lower for w in ['хлеб', 'батон', 'булк', 'лаваш', 'non', 'хрус', 'nonqoqi']):
        return "🍞 Хлеб и выпечка"
    
    if any(w in name_lower for w in ['молоко', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр', 'масл', 'sut', 'yogurt']):
        return "🥛 Молочные продукты"
    
    if any(w in name_lower for w in ['мясо', 'куриц', 'говяд', 'рыб', 'колбас', 'сосиск', "go'sht", 'tovuq', 'baliq']):
        return "🥩 Мясо и рыба"
    
    if any(w in name_lower for w in ['помидор', 'огурец', 'картоф', 'морков', 'яблок', 'банан', 'sabzavot', 'meva']):
        return "🥗 Овощи и фрукты"
    
    if any(w in name_lower for w in ['рис', 'гречк', 'макарон', 'спагетт', 'мука', 'паста', 'guruch', 'makaron']):
        return "🍝 Крупы и макароны"
    
    if any(w in name_lower for w in ['лекарств', 'таблетк', 'витамин', 'мазь', 'шампун', 'мыло', 'зубн', 'dori', 'shampon']):
        return "💊 Медицина и гигиена"
    
    if any(w in name_lower for w in ['порошок', 'чист', 'средств', 'пакет', 'sumka', 'polieti', 'paket', 'логотипл', 'bio']):
        return "🧹 Бытовая химия"
    
    return "🎁 Другое"

def parse_price(price_str):
    try:
        clean = re.sub(r'[^\d,.]', '', price_str).replace(',', '')
        return float(clean)
    except:
        return 0.0

def calculate_statistics(receipts):
    category_stats = {cat: {"total": 0, "count": 0, "products": []} for cat in CATEGORIES.keys()}
    total_spent = 0
    
    for receipt in receipts:
        for product in receipt.get('products', []):
            category = product.get('category', '🎁 Другое')
            price = parse_price(product.get('price', '0'))
            
            category_stats[category]['total'] += price
            category_stats[category]['count'] += 1
            category_stats[category]['products'].append({
                'name': product['name'],
                'price': price,
                'receipt': receipt['receiptNumber']
            })
            total_spent += price
    
    category_stats = {k: v for k, v in category_stats.items() if v['count'] > 0}
    category_stats = dict(sorted(category_stats.items(), key=lambda x: x[1]['total'], reverse=True))
    
    return {
        'categories': category_stats,
        'total': total_spent,
        'receipts_count': len(receipts)
    }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    stats = calculate_statistics(receipts_storage)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "receipts": receipts_storage,
        "receipts_json": json.dumps(receipts_storage, ensure_ascii=False),
        "stats": stats
    })

@app.get("/api/receipts")
async def get_receipts():
    return {"receipts": receipts_storage}

@app.get("/api/statistics")
async def get_statistics():
    return calculate_statistics(receipts_storage)

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
        
        company = "Неизвестно"
        h3_bold = soup.find('h3', style=lambda x: x and 'font-weight' in x and 'bold' in x)
        if h3_bold:
            company = h3_bold.get_text(strip=True)
        
        receipt_num = "N/A"
        first_b = soup.find('td')
        if first_b:
            first_b = first_b.find('b')
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
                product_name = name_td.get_text(strip=True)
                products.append({
                    'name': product_name,
                    'quantity': qty_td.get_text(strip=True),
                    'price': price_td.get_text(strip=True),
                    'category': categorize_simple(product_name)
                })
        
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

# Для Vercel (ОБЯЗАТЕЛЬНО!)
app = app
