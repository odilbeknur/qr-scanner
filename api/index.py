import sys
import os

# Добавляем корневую директорию в path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

# Vercel handler
handler = app