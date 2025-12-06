#!/usr/bin/env python3
"""
Точка входа для запуска приложения
"""

import os
import sys

# Добавляем текущую директорию в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Пытаемся импортировать обычным способом
try:
    from app import create_app
    print("✅ Модуль app успешно импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Проверьте структуру проекта:")
    print("1. Убедитесь, что файл app/__init__.py существует")
    print("2. Проверьте, что все зависимости установлены")
    print("3. Текущая структура:")
    for root, dirs, files in os.walk(current_dir):
        level = root.replace(current_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files[:5]:  # Показываем первые 5 файлов
            if file.endswith('.py'):
                print(f"{subindent}{file}")
    sys.exit(1)

# Создание приложения
try:
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    print("✅ Приложение успешно создано")
except Exception as e:
    print(f"❌ Ошибка при создании приложения: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == '__main__':
    # Запуск сервера
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'

    print(f"🚀 Запуск Skill Matrix API на {host}:{port}")
    print(f"🌍 Режим: {app.config.get('FLASK_ENV', 'development')}")
    print(f"🐞 Debug: {debug}")

    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as e:
        print(f"❌ Ошибка при запуске сервера: {e}")
        sys.exit(1)
