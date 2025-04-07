from flask import Flask
from flask_cors import CORS
import os
from dotenv import load_dotenv


# Загрузка переменных окружения из .env файла
load_dotenv()


def create_app(test_config=None):
    """
    Фабрика приложения Flask, создающая и настраивающая экземпляр Flask
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Настройка CORS
    CORS(app)
    
    # Загрузка конфигурации
    if test_config is None:
        # Загрузка конфигурации из environment variables
        app.config.from_mapping(
            SECRET_KEY=os.environ.get('APP_SECRET_KEY', 'dev'),
            DEBUG=os.environ.get('DEBUG', 'False') == 'True',
        )
    else:
        # Загрузка тестовой конфигурации
        app.config.from_mapping(test_config)
    
    
    # Регистрация маршрутов
    from app.api import routes
    app.register_blueprint(routes.bp)
    
    return app

# Создание экземпляра приложения для запуска через WSGI
app = create_app()
