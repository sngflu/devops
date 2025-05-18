import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from app import create_app
from app.services.minio import MinioStorage

@pytest.fixture
def app():
    """Создает и настраивает экземпляр Flask для тестирования."""
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test'
    })
    
    yield app

@pytest.fixture
def client(app):
    """Создает тестовый клиент для приложения."""
    return app.test_client()

def test_app_works(client):
    """Проверяет, что приложение запускается и отвечает на запросы."""
    response = client.get('/health')
    assert response.status_code == 200
    
def test_login_route_exists(client):
    """Проверяет, что маршрут /login существует и принимает POST запросы."""
    response = client.post('/login', json={
        'username': 'testuser',
        'password': 'testpassword'
    })
    # В режиме тестирования с моками мы ожидаем успешный ответ
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data

@pytest.fixture
def mock_minio_storage():
    with patch('app.services.minio.MinioStorage') as mock_storage:
        mock_instance = MagicMock()
        mock_storage.return_value = mock_instance
        
        mock_instance.save_video.return_value = True
        mock_instance.save_log.return_value = True
        mock_instance.get_presigned_url.return_value = "https://minio.example.com/videos/test_video.mp4"
        mock_instance.get_log.return_value = [(0, 1, 0), (1, 0, 1)]
        mock_instance.list_user_videos.return_value = [
            {"filename": "test_user_20230101_video.mp4", "original_name": "video.mp4", "log_count": 2}
        ]
        mock_instance.delete_objects.return_value = True
        mock_instance.rename_object.return_value = True
        
        yield mock_instance

@pytest.fixture
def authenticated_client(client):
    """Создает аутентифицированный клиент для тестирования защищенных маршрутов."""
    client.post('/register', json={'username': 'testuser', 'password': 'testpassword'})
    
    response = client.post('/login', json={'username': 'testuser', 'password': 'testpassword'})
    token = json.loads(response.data)['token']
    
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    return client

def test_video_upload_to_minio(authenticated_client, test_video_file):
    """Проверяет загрузку видео в MinIO."""
    with open(test_video_file, 'rb') as video_file:
        response = authenticated_client.post(
            '/predict',
            data={'file': (video_file, 'test_video.mp4')},
            content_type='multipart/form-data'
        )
            
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'video_url' in data
    assert 'frame_objects' in data
    assert 'fps' in data

def test_get_video_from_minio(authenticated_client):
    """Проверяет получение видео из MinIO."""
    response = authenticated_client.get('/video/testuser_video.mp4')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'url' in data
    assert data['url'] == "https://example.com/video.mp4"

def test_delete_video_from_minio(authenticated_client):
    """Проверяет удаление видео из MinIO."""
    response = authenticated_client.delete('/videos/testuser_video.mp4')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Successfully deleted" 