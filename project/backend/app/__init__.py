from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
from dotenv import load_dotenv
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Histogram


# Определение метрик Prometheus
# Эта гистограмма будет измерять задержку ответа на HTTP-запросы.
# Метка 'endpoint' будет содержать путь запрошенного эндпоинта.
request_latency = Histogram(
    'request_latency_seconds', 
    'Request latency in seconds', 
    ['endpoint']
)

# Загрузка переменных окружения из .env файла
load_dotenv()

# Глобальный экземпляр метрик для доступа из других модулей
metrics = None

def create_app(test_config=None):
    """
    Фабрика приложения Flask, создающая и настраивающая экземпляр Flask
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Настройка CORS
    CORS(app)
    
    # Инициализация Prometheus метрик
    global metrics
    metrics = PrometheusMetrics(app, path='/metrics')
    
    # Включаем экспорт стандартных метрик Flask
    metrics.info('app_info', 'Application info', version='1.0.0')
    
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
    
    # Обработчики для кастомной метрики request_latency
    @app.before_request
    def before_request_timing():
        request.start_time = time.time()

    @app.after_request
    def after_request_timing(response):
        if hasattr(request, 'start_time'): # Убедимся, что start_time было установлено
            latency = time.time() - request.start_time
            request_latency.labels(endpoint=request.path).observe(latency)
        return response
    
    # Регистрация маршрутов
    from app.api import routes
    app.register_blueprint(routes.bp)
    
    # После регистрации всех маршрутов регистрируем дефолтные метрики
    # для отслеживания запросов по путям
    with app.app_context():
        metrics.register_default(
            metrics.counter(
                'by_path_counter', 'Request count by request paths',
                labels={'path': lambda: request.path}
            )
        )
    
    return app

# Создание экземпляра приложения для запуска через WSGI
app = create_app()
