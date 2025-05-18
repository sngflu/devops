import pytest
import os
import tempfile
import json
import jwt
from unittest.mock import patch, MagicMock
from app import create_app
from datetime import datetime
import numpy as np

TEST_SECRET_KEY = "test_secret_key"

@pytest.fixture
def app():
    """Создает и настраивает экземпляр Flask для тестирования."""
    with patch('app.api.routes.SECRET_KEY', TEST_SECRET_KEY), \
         patch('app.api.routes.DatabaseManager') as mock_db_manager, \
         patch('app.api.routes.MinioStorage') as mock_minio:
        
        mock_db_instance = MagicMock()
        mock_db_manager.return_value = mock_db_instance
        
        mock_storage_instance = MagicMock()
        mock_minio.return_value = mock_storage_instance
        
        app = create_app({
            'TESTING': True,
            'SECRET_KEY': TEST_SECRET_KEY
        })
        
        app.db_manager = mock_db_instance
        app.storage = mock_storage_instance
        
        # Настраиваем моки для database
        app.db_manager.init_database.return_value = True
        app.db_manager.create_user.return_value = 1
        app.db_manager.get_user_by_username.return_value = {
            'id': 1, 'username': 'testuser', 'password_hash': 'hash'
        }
        app.db_manager.save_video_metadata.return_value = True
        app.db_manager.get_user_videos.return_value = [
            {'filename': 'test.mp4', 'original_name': 'test.mp4', 'timestamp': '2023-01-01 12:00:00'}
        ]
        app.db_manager.delete_video.return_value = True
        
        # Настраиваем моки для minio storage
        app.storage.save_video.return_value = 'testuser_20230101_video.mp4'
        app.storage.save_log.return_value = 'testuser_20230101_video.json'
        app.storage.get_presigned_url.return_value = 'https://example.com/video.mp4'
        app.storage.get_log.return_value = [[0, 0.8, "person"], [1, 0.7, "car"]]
        app.storage.delete_objects.return_value = True
        
        # Настраиваем мок для video processing
        with patch('app.api.routes.video_processing.process_video') as mock_process:
            mock_process.return_value = (
                'testuser_20230101_video.mp4',  # video_filename
                [[0, 0.8, "person"], [1, 0.7, "car"]],  # frame_objects
                30,  # fps
                False,  # has_weapon
                'testuser_20230101_video.json'  # log_filename
            )
            app.process_video = mock_process
        
        yield app

@pytest.fixture
def client(app):
    """Создает тестовый клиент для приложения."""
    return app.test_client()

@pytest.fixture
def auth_token():
    """Создает JWT токен для тестов."""
    return jwt.encode(
        {"user": "testuser", "user_id": "user123"},
        TEST_SECRET_KEY
    )

@pytest.fixture
def auth_headers(auth_token):
    """Создает заголовки авторизации."""
    return {'Authorization': f'Bearer {auth_token}'}

@pytest.fixture
def authenticated_client(client, auth_token):
    """Создает аутентифицированный клиент для тестирования защищенных маршрутов."""
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {auth_token}'
    return client

@pytest.fixture
def test_video_file():
    """Создает временный видеофайл для тестирования."""
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    temp_file.write(b"test video content")
    temp_file.close()
    
    yield temp_file.name
    
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)

@pytest.fixture
def test_log_file():
    """Создает временный JSON-файл с логами для тестирования."""
    temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
    
    log_data = [
        [0, 0.8, 10, 10, 50, 50, "person"],
        [1, 0.7, 100, 100, 150, 150, "car"]
    ]
    
    json.dump(log_data, temp_file)
    temp_file.close()
    
    yield temp_file.name
    
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)

@pytest.fixture
def mock_db_manager():
    """Создает мок для DatabaseManager."""
    with patch('app.services.database.db.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.__enter__.return_value = mock_cursor
        
        from app.services.database import DatabaseManager
        manager = DatabaseManager()
        
        manager._mock_conn = mock_conn
        manager._mock_cursor = mock_cursor
        
        yield manager

@pytest.fixture
def mock_minio_storage():
    """Создает мок для MinioStorage."""
    with patch('app.services.minio.minio_client.Minio') as mock_minio_client:
        mock_client = MagicMock()
        mock_minio_client.return_value = mock_client
        
        mock_client.bucket_exists.return_value = True
        mock_client.put_object.return_value = True
        mock_client.presigned_get_object.return_value = "https://minio.example.com/test-bucket/test-object"
        mock_client.remove_object.return_value = None
        mock_client.copy_object.return_value = None
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'minio:9000',
            'MINIO_ACCESS_KEY': 'minioadmin',
            'MINIO_SECRET_KEY': 'minioadmin',
            'MINIO_VIDEOS_BUCKET': 'videos',
            'MINIO_LOGS_BUCKET': 'logs'
        }):
            from app.services.minio import MinioStorage
            storage = MinioStorage()
            
            storage._mock_client = mock_client
            
            yield storage

@pytest.fixture
def mock_yolo_model():
    """Создает мок для модели YOLO."""
    with patch('app.models.model.YOLO') as mock_yolo_class:
        mock_model = MagicMock()
        mock_yolo_class.return_value = mock_model
        
        mock_result = MagicMock()
        mock_result.boxes.cls = np.array([0, 1])
        mock_result.boxes.conf = np.array([0.8, 0.7])
        mock_result.boxes.xyxy = np.array([
            [10, 10, 50, 50],
            [100, 100, 150, 150]
        ])
        
        mock_model.predict.return_value = [mock_result]
        
        with patch('app.models.model.model', mock_model):
            yield mock_model

@pytest.fixture
def mock_datetime():
    """Создает мок для datetime с фиксированной датой/временем."""
    with patch('app.services.video_processing.video_processing.datetime') as mock_dt:
        fixed_date = datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.now.return_value = fixed_date
        mock_dt.strftime = datetime.strftime
        yield mock_dt 