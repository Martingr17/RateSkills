#!/usr/bin/env python3
"""
Точка входа для запуска приложения
"""

import os
from app import create_app

# Создание приложения
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    # Запуск сервера
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    print(f"Starting Skill Matrix API server on {host}:{port}")
    print(f"Environment: {app.config['FLASK_ENV']}")
    print(f"Debug mode: {debug}")
    
    app.run(host=host, port=port, debug=debug)