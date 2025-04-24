import pytest
import json
import os
import jwt
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, ANY
from app import create_app

# Чтение секретного ключа из тестового окружения
TEST_SECRET_KEY = "test_secret_key"

@pytest.fixture
def app():
    """Создает и настраивает экземпляр Flask для тестирования."""
    with patch('app.api.routes.SECRET_KEY', TEST_SECRET_KEY):
        app = create_app({
            'TESTING': True,
            'SECRET_KEY': TEST_SECRET_KEY
        })
        
        mock_db_manager = MagicMock()
        mock_storage = MagicMock()
        
        app.db_manager = mock_db_manager
        app.storage = mock_storage
        
        with patch('app.api.routes.db_manager', mock_db_manager), \
             patch('app.api.routes.storage', mock_storage):
            
            yield app

@pytest.fixture
def client(app):
    """Создает тестовый клиент для приложения."""
    return app.test_client()

@pytest.fixture
def test_username():
    """Имя тестового пользователя."""
    return "testuser"

@pytest.fixture
def test_user_id():
    """Создает UUID для тестового пользователя."""
    return uuid.uuid4()

@pytest.fixture
def auth_token(test_username, test_user_id):
    """Создает JWT токен для тестов."""
    return jwt.encode(
        {"user": test_username, "user_id": str(test_user_id)},
        TEST_SECRET_KEY,
        algorithm="HS256"
    )

@pytest.fixture
def auth_headers(auth_token):
    """Создает заголовки авторизации."""
    return {'Authorization': f'Bearer {auth_token}'}

@pytest.fixture
def test_video_filename(test_username):
    """Создает тестовое имя файла с префиксом пользователя."""
    return f"{test_username}_20230101_120000_test_video.mp4"

@pytest.fixture
def test_log_filename(test_video_filename):
    """Создает тестовое имя файла лога."""
    return f"{test_video_filename}.json"

def test_register_success(client, app):
    """Тестирует успешную регистрацию пользователя."""
    app.db_manager.get_user_by_username.return_value = None
    
    test_user_id = uuid.uuid4()
    app.db_manager.create_user.return_value = (test_user_id, None)
    
    response = client.post('/register', 
                         json={'username': 'testuser', 'password': 'testpassword'})
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'token' in data
    
    app.db_manager.get_user_by_username.assert_called_with('testuser')
    app.db_manager.create_user.assert_called_with('testuser', ANY)

def test_register_existing_user(client, app):
    """Тестирует попытку регистрации существующего пользователя."""
    app.db_manager.get_user_by_username.return_value = {
        "user_id": uuid.uuid4(),
        "username": "testuser",
        "password_hash": "hashed_password"
    }
    
    response = client.post('/register', 
                         json={'username': 'testuser', 'password': 'testpassword'})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'message' in data
    assert 'already exists' in data['message']

def test_login_success(client, app):
    """Тестирует успешный вход пользователя."""
    app.db_manager.get_user_by_username.return_value = {
        "user_id": uuid.uuid4(),
        "username": "testuser",
        "password_hash": "hashed_password"
    }
    
    with patch('app.api.routes.check_password_hash') as mock_check_password:
        mock_check_password.return_value = True
        
        response = client.post('/login', 
                             json={'username': 'testuser', 'password': 'testpassword'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data
        
        app.db_manager.get_user_by_username.assert_called_with('testuser')
        mock_check_password.assert_called()

def test_login_invalid_credentials(client, app):
    """Тестирует вход с неверными учетными данными."""
    app.db_manager.get_user_by_username.return_value = {
        "user_id": uuid.uuid4(),
        "username": "testuser",
        "password_hash": "hashed_password"
    }
    
    with patch('app.api.routes.check_password_hash') as mock_check_password:
        mock_check_password.return_value = False
        
        response = client.post('/login', 
                             json={'username': 'testuser', 'password': 'wrong_password'})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'message' in data
        assert 'Invalid credentials' in data['message']

def test_login_user_not_found(client, app):
    """Тестирует вход с несуществующим пользователем."""
    app.db_manager.get_user_by_username.return_value = None
    
    response = client.post('/login', 
                         json={'username': 'nonexistentuser', 'password': 'testpassword'})
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'message' in data
    assert 'Invalid credentials' in data['message']

def test_get_videos_success(client, app, auth_headers, test_username, test_user_id):
    """Тестирует успешное получение списка видео."""
    upload_time1 = datetime(2023, 1, 1, 0, 0, 0)
    upload_time2 = datetime(2023, 1, 2, 0, 0, 0)
    
    test_videos = [
        {
            "video_id": uuid.uuid4(),
            "s3_key": f"{test_username}_20230101_120000_video1.mp4",
            "upload_time": upload_time1,
            "status": "completed",
            "weapon_detected": False
        },
        {
            "video_id": uuid.uuid4(),
            "s3_key": f"{test_username}_20230101_120000_video2.mp4",
            "upload_time": upload_time2,
            "status": "completed",
            "weapon_detected": True
        }
    ]
    app.db_manager.get_user_videos.return_value = test_videos
    
    app.storage.list_user_videos.return_value = []
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        
        response = client.get('/videos', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        
        mock_jwt_decode.assert_called_with(auth_headers['Authorization'].split()[1], TEST_SECRET_KEY, algorithms=["HS256"])
        app.db_manager.get_user_videos.assert_called_with(str(test_user_id))
        app.storage.list_user_videos.assert_called_with(test_username)

def test_get_videos_error(client, app, auth_headers, test_username, test_user_id):
    """Тестирует обработку ошибок при получении списка видео."""
    db_error = "Database error"
    app.db_manager.get_user_videos.side_effect = Exception(db_error)
    
    app.storage.list_user_videos.return_value = []
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        
        response = client.get('/videos', headers=auth_headers)
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

def test_get_video_logs_success(client, app, auth_headers, test_username, test_user_id, test_video_filename, test_log_filename):
    """Тестирует успешное получение логов видео."""
    video_id = uuid.uuid4()
    
    app.db_manager.get_video_by_s3_key.return_value = {
        "video_id": video_id,
        "user_id": test_user_id,
        "s3_key": test_video_filename
    }
    
    app.db_manager.get_video_detections.return_value = None
    
    mock_logs = [
        [0, 1, 0],
        [1, 0, 1]
    ]
    app.storage.get_log.return_value = mock_logs
    
    app.storage.object_exists.return_value = False
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        
        response = client.get(f'/videos/{test_video_filename}/logs', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0] == [0, 1, 0]
        assert data[1] == [1, 0, 1]
        
        app.storage.get_log.assert_called_with(test_log_filename)

def test_get_video_logs_not_found(client, app, auth_headers, test_username, test_user_id, test_video_filename, test_log_filename):
    """Тестирует получение логов несуществующего видео."""
    video_id = uuid.uuid4()
    
    app.db_manager.get_video_by_s3_key.return_value = {
        "video_id": video_id,
        "user_id": test_user_id,
        "s3_key": test_video_filename
    }
    
    app.db_manager.get_video_detections.return_value = None
    
    app.storage.get_log.return_value = None
    
    app.storage.object_exists.return_value = False
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        
        response = client.get(f'/videos/{test_video_filename}/logs', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert 'not found' in data['error']

def test_delete_video_success(client, app, auth_headers, test_username, test_user_id, test_video_filename):
    """Тестирует успешное удаление видео."""
    video_id = uuid.uuid4()
    
    app.db_manager.get_video_by_s3_key.return_value = {
        "video_id": video_id,
        "user_id": test_user_id,
        "s3_key": test_video_filename
    }
    
    app.db_manager.delete_video.return_value = (True, None)
    
    app.storage.delete_objects.return_value = True
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode, \
         patch('app.api.routes.uuid.UUID') as mock_uuid:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        mock_uuid.side_effect = lambda x: x if isinstance(x, uuid.UUID) else test_user_id
        
        response = client.delete(f'/videos/{test_video_filename}', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data
        assert 'Successfully deleted' in data['message']
        
       
def test_update_video_success(client, app, auth_headers, test_username, test_user_id, test_video_filename):
    """Тестирует успешное обновление видео."""
    new_name = "new_video_name.mp4"
    expected_new_filename = f"{test_username}_20230101_120000_{new_name}"
    
    video_id = uuid.uuid4()
    
    app.db_manager.get_video_by_s3_key.return_value = {
        "video_id": video_id,
        "user_id": test_user_id,
        "s3_key": test_video_filename
    }
    
    app.db_manager.rename_video.return_value = (True, None)
    
    app.storage.rename_object.return_value = True
    
    with patch('app.api.routes.jwt.decode') as mock_jwt_decode:
        mock_jwt_decode.return_value = {"user": test_username, "user_id": str(test_user_id)}
        
        response = client.put(
            f'/videos/{test_video_filename}',
            json={'new_name': new_name},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data
        assert 'renamed successfully' in data['message'] 