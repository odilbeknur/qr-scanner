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

# Путь к шаблонам
template_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_path))

# Временное хранилище
receipts_storage = []

# Кэш категорий (чтобы не спрашивать AI повторно)
category_cache = {}

# Основные категории
CATEGORIES = {
    "🍬 Сладости": "сладости, десерты, печенье, шоколад, конфеты",
    "🥤 Напитки": "напитки, вода, сок, газировка, чай, кофе",
    "🍞 Хлеб и выпечка": "хлеб, булки, выпечка, батоны",
    "🥛 Молочные продукты": "молоко, кефир, йогурт, сыр, творог",
    "🥩 Мясо и рыба": "мясо, курица, рыба, колбаса",
    "🥗 Овощи и фрукты": "овощи, фрукты, зелень",
    "🍝 Крупы и макароны": "крупы, макароны, рис, гречка",
    "💊 Медицина и гигиена": "лекарства, витамины, шампунь, мыло",
    "🧹 Бытовая химия": "моющие средства, порошок, пакеты",
    "🎁 Другое": "прочие товары"
}

async def categorize_with_ai(product_name):
    """Категоризация через Gemini API"""
    
    # Проверяем кэш
    name_lower = product_name.lower()
    if name_lower in category_cache:
        return category_cache[name_lower]
    
    # Простая эвристика (без AI для базовых случаев)
    category = categorize_simple(product_name)
    if category != "🎁 Другое":
        category_cache[name_lower] = category
        return category
    
    # Используем Gemini AI для сложных случаев
    api_key = os.getenv("   ", "")
    if not api_key:
        category_cache[name_lower] = category
        return category
    
    try:
        categories_text = ", ".join([f"{cat}" for cat in CATEGORIES.keys() if cat != "🎁 Другое"])
        
        prompt = f"""Определи категорию товара. Отвечай ТОЛЬКО названием категории из списка.

Категории: {categories_text}

Товар: {product_name}

Ответ (только категория с эмодзи):"""

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 20
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Находим категорию
                for cat_name in CATEGORIES.keys():
                    if cat_name in ai_response or ai_response in cat_name:
                        category_cache[name_lower] = cat_name
                        return cat_name
    except Exception as e:
        print(f"AI error: {e}")
    
    # Fallback на простую категоризацию
    category_cache[name_lower] = category
    return category

def categorize_simple(product_name):
    """Простая категоризация по ключевым словам"""
    name_lower = product_name.lower()
    
    # Сладости
    if any(word in name_lower for word in [
        'печенье', 'шоколад', 'конфет', 'торт', 'пирожн', 'вафл', 'браун',
        'pechenye', 'shokolad', 'brauni', 'cushion', 'cookie', 'cake'
    ]):
        return "🍬 Сладости"
    
    # Напитки
    if any(word in name_lower for word in [
        'сок', 'вод', 'чай', 'кофе', 'лимонад', 'cola', 'fanta', 'sprite',
        'ichimlik', 'drink', 'напит', 'juice', 'dyushes', 'pet'
    ]):
        return "🥤 Напитки"
    
    # Хлеб
    if any(word in name_lower for word in [
        'хлеб', 'батон', 'булк', 'лаваш', 'non', 'bread', 'хрус', 'bar'
    ]):
        return "🍞 Хлеб и выпечка"
    
    # Молочка
    if any(word in name_lower for word in [
        'молоко', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр', 'масл',
        'sut', 'yogurt', 'milk', 'cheese'
    ]):
        return "🥛 Молочные продукты"
    
    # Мясо/рыба
    if any(word in name_lower for word in [
        'мясо', 'куриц', 'говяд', 'рыб', 'колбас', 'сосиск',
        'go\'sht', 'tovuq', 'baliq', 'meat', 'chicken'
    ]):
        return "🥩 Мясо и рыба"
    
    # Овощи/фрукты
    if any(word in name_lower for word in [
        'помидор', 'огурец', 'картоф', 'морков', 'яблок', 'банан',
        'sabzavot', 'meva', 'fruit', 'vegetable'
    ]):
        return "🥗 Овощи и фрукты"
    
    # Крупы
    if any(word in name_lower for word in [
        'рис', 'гречк', 'макарон', 'спагетт', 'мука', 'паста',
        'guruch', 'makaron', 'pasta', 'rice'
    ]):
        return "🍝 Крупы и макароны"
    
    # Медицина/гигиена
    if any(word in name_lower for word in [
        'лекарств', 'таблетк', 'витамин', 'мазь', 'шампун', 'мыло', 'зубн',
        'dori', 'shampon', 'sovun', 'medicine'
    ]):
        return "💊 Медицина и гигиена"
    
    # Бытовая химия
    if any(word in name_lower for word in [
        'порошок', 'чист', 'средств', 'пакет', 'sumka', 'polieti',
        'paket', 'bag', 'логотипл', 'bio'
    ]):
        return "🧹 Бытовая химия"
    
    return "🎁 Другое"

def categorize_product(product_name):
    """Синхронная обертка для категоризации"""
    return categorize_simple(product_name)

def parse_price(price_str):
    """Извлекает числовое значение из строки цены"""
    try:
        # Удаляем всё кроме цифр, точек и запятых
        clean = re.sub(r'[^\d,.]', '', price_str)
        # Заменяем запятую на точку
        clean = clean.replace(',', '')
        return float(clean)
    except:
        return 0.0

def calculate_statistics(receipts):
    """Вычисляет статистику по категориям"""
    category_stats = {}
    for cat in CATEGORIES.keys():
        category_stats[cat] = {"total": 0, "count": 0, "products": []}
    
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
    
    # Удаляем пустые категории
    category_stats = {k: v for k, v in category_stats.items() 
                      if v['count'] > 0}
    
    # Сортируем по сумме (убывание)
    category_stats = dict(sorted(category_stats.items(), 
                                 key=lambda x: x[1]['total'], 
                                 reverse=True))
    
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
                product_name = name_td.get_text(strip=True)
                products.append({
                    'name': product_name,
                    'quantity': qty_td.get_text(strip=True),
                    'price': price_td.get_text(strip=True),
                    'category': categorize_product(product_name)
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

# Для Vercel (ОБЯЗАТЕЛЬНО!)
handler = app