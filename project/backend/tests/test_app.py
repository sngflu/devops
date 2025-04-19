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
    response = client.get('/')
    assert response.status_code == 404
    
def test_login_route_exists(client):
    """Проверяет, что маршрут /login существует и принимает POST запросы."""
    response = client.post('/login', json={
        'username': 'test',
        'password': 'test'
    })
    assert response.status_code == 401 

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

def test_video_upload_to_minio(authenticated_client):
    """Проверяет загрузку видео в MinIO."""
    with patch('app.api.routes.video_processing.process_video') as mock_process, \
         patch('app.api.routes.storage') as mock_storage:
        
        video_filename = 'testuser_20230101_video.mp4'
        frame_objects = [[0, 0.8, 10, 10, 50, 50, "person"], [1, 0.7, 100, 100, 150, 150, "car"]]
        fps = 30
        has_weapon = False
        log_filename = 'testuser_20230101_video.json'
        
        mock_process.return_value = (video_filename, frame_objects, fps, has_weapon, log_filename)
        
        mock_storage.get_presigned_url.return_value = f"https://minio.example.com/videos/{video_filename}"
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_video:
            temp_video.write(b'test video content')
            temp_video.flush()
            
            with open(temp_video.name, 'rb') as video_file:
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
            
            mock_process.assert_called_once()

@patch('app.api.routes.storage')
def test_get_video_from_minio(mock_storage, authenticated_client):
    """Проверяет получение видео из MinIO."""
    mock_storage.get_presigned_url.return_value = "https://minio.example.com/videos/testuser_video.mp4"
    
    response = authenticated_client.get('/video/testuser_video.mp4')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'url' in data
    assert data['url'] == "https://minio.example.com/videos/testuser_video.mp4"
    
    mock_storage.get_presigned_url.assert_called_once_with("testuser_video.mp4")

@patch('app.api.routes.storage')
def test_delete_video_from_minio(mock_storage, authenticated_client):
    """Проверяет удаление видео из MinIO."""
    mock_storage.delete_objects.return_value = True
    
    response = authenticated_client.delete('/videos/testuser_video.mp4')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Successfully deleted"
    
    mock_storage.delete_objects.assert_called_once_with('testuser_video.mp4', 'testuser_video.mp4.json') 