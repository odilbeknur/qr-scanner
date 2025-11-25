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
    "🍿 Снеки и чипсы": [],
    "💊 Медицина и здоровье": [],
    "🧴 Гигиена и косметика": [],
    "🧹 Бытовая химия": [],
    "🎁 Другое": []
}

def categorize_simple(product_name):
    name_lower = product_name.lower()
    
    # Сладости (кондитерские изделия)
    if any(w in name_lower for w in [
        'печенье', 'шоколад', 'конфет', 'торт', 'пирожн', 'вафл', 'браун',
        'pechenye', 'shokolad', 'brauni', 'cushion', 'cookie', 'cake',
        'зефир', 'мармелад', 'халва', 'карамел', 'ирис', 'драже'
    ]):
        return "🍬 Сладости"
    
    # Снеки и чипсы (соленое, хрустящее)
    if any(w in name_lower for w in [
        'чипс', 'сухар', 'хрустим', 'крекер', 'попкорн', 'снек',
        'chips', 'cracker', 'сухарик', 'хрус', 'crisp', 'флипс',
        'соломк', 'семечк', 'орех', 'арахис', 'фисташк'
    ]):
        return "🍿 Снеки и чипсы"
    
    # Напитки
    if any(w in name_lower for w in [
        'сок', 'вод', 'чай', 'кофе', 'лимонад', 'cola', 'fanta', 'sprite',
        'ichimlik', 'drink', 'напит', 'juice', 'dyushes', 'pet', 'газир',
        'энергетик', 'квас', 'морс', 'компот', 'нектар'
    ]):
        return "🥤 Напитки"
    
    # Хлеб (ТОЛЬКО свежая выпечка, не сухари!)
    if any(w in name_lower for w in [
        'хлеб', 'батон', 'булк', 'лаваш', 'non', 'bread', 'бейгл',
        'багет', 'тост', 'слойк', 'рогалик', 'пирог', 'самса'
    ]) and 'хрус' not in name_lower and 'сухар' not in name_lower:
        return "🍞 Хлеб и выпечка"
    
    # Молочка
    if any(w in name_lower for w in [
        'молоко', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр', 'масл',
        'sut', 'yogurt', 'milk', 'cheese', 'ряженк', 'айран', 'тан',
        'простокваш', 'сливк'
    ]):
        return "🥛 Молочные продукты"
    
    # Мясо/рыба
    if any(w in name_lower for w in [
        'мясо', 'куриц', 'говяд', 'рыб', 'колбас', 'сосиск', 'бекон',
        "go'sht", 'tovuq', 'baliq', 'meat', 'chicken', 'свинин',
        'фарш', 'котлет', 'пельмен', 'манты'
    ]):
        return "🥩 Мясо и рыба"
    
    # Овощи/фрукты
    if any(w in name_lower for word in [
        'помидор', 'огурец', 'картоф', 'морков', 'яблок', 'банан',
        'sabzavot', 'meva', 'fruit', 'vegetable', 'капуст', 'лук',
        'свекл', 'редис', 'перец', 'баклажан', 'кабачок', 'салат',
        'апельсин', 'мандарин', 'груш', 'виноград', 'ягод'
    ]):
        return "🥗 Овощи и фрукты"
    
    # Крупы
    if any(w in name_lower for w in [
        'рис', 'гречк', 'макарон', 'спагетт', 'мука', 'паста',
        'guruch', 'makaron', 'pasta', 'rice', 'овся', 'перлов',
        'манн', 'пшен', 'булгур', 'кус-кус', 'вермишел'
    ]):
        return "🍝 Крупы и макароны"
    
    # Медицина и здоровье (лекарства, медизделия)
    if any(w in name_lower for w in [
        'таблетк', 'витамин', 'лекарств', 'капсул', 'сироп', 'мазь',
        'dori', 'medicine', 'пластыр', 'бинт', 'вата', 'шприц',
        'термометр', 'градусник', 'тонометр', 'аспирин', 'парацетамол',
        'анальгин', 'цитрамон', 'активир', 'уголь', 'но-шпа',
        'смект', 'линекс', 'бад', 'препарат', 'капл', 'спрей'
    ]):
        return "💊 Медицина и здоровье"
    
    # Гигиена и косметика (личная гигиена)
    if any(w in name_lower for w in [
        'шампун', 'мыло', 'гель', 'крем', 'зубн', 'паст', 'щетк',
        'shampon', 'sovun', 'дезодорант', 'бальзам', 'кондиционер',
        'пена', 'скраб', 'лосьон', 'маск', 'сыворотк', 'тоник',
        'прокладк', 'тампон', 'памперс', 'подгузник', 'салфетк',
        'туалетн', 'бумаг', 'влажн', 'полотенц'
    ]):
        return "🧴 Гигиена и косметика"
    
    # Бытовая химия (для уборки и стирки)
    if any(w in name_lower for w in [
        'порошок', 'чист', 'средств', 'пакет', 'sumka', 'polieti',
        'paket', 'bag', 'логотипл', 'bio', 'моющ', 'отбелив',
        'ополаскив', 'кондиционер', 'мешок', 'губк', 'тряпк',
        'освежител', 'fairy', 'gala', 'persil', 'ariel'
    ]):
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
