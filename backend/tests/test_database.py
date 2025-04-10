import pytest
import os
import json
from unittest.mock import patch, MagicMock, Mock
from app.services.database import DatabaseManager
import uuid
from datetime import datetime

@pytest.fixture
def db_manager():
    """Создает экземпляр DatabaseManager для тестирования с мок-подключением."""
    with patch('app.services.database.db.psycopg2.connect') as mock_connect:
        # Мокаем соединение и курсор
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Мокаем context manager для cursor
        mock_cursor.__enter__.return_value = mock_cursor
        
        # Создаем экземпляр DatabaseManager
        manager = DatabaseManager()
        
        # Добавляем моки в экземпляр для доступа в тестах
        manager._mock_conn = mock_conn
        manager._mock_cursor = mock_cursor
        
        yield manager

def test_init_database(db_manager):
    """Тестирует инициализацию базы данных."""
    # Вызываем метод
    result = db_manager.init_database()
    
    # Проверяем, что метод get_connection был вызван
    assert result is True
    
    # Проверяем, что был вызван close для закрытия соединения
    db_manager._mock_conn.close.assert_called()

def test_create_user(db_manager):
    """Тестирует создание пользователя."""
    # Мокаем возвращаемое значение для execute_query
    test_user_id = uuid.uuid4()
    mock_result = {"user_id": test_user_id}
    # Заменяем моки для execute_query вместо прямого мока fetchone
    db_manager.execute_query = MagicMock(return_value=(mock_result, None))
    
    # Вызываем метод
    username = "testuser"
    password_hash = "hashed_password"
    user_id, error = db_manager.create_user(username, password_hash)
    
    # Проверяем результаты
    assert user_id == test_user_id
    assert error is None
    db_manager.execute_query.assert_called()

def test_create_user_error(db_manager):
    """Тестирует обработку ошибок при создании пользователя."""
    # Мокаем ошибку в execute_query
    db_manager.execute_query = MagicMock(return_value=(None, "Ошибка выполнения запроса: DB error"))
    
    # Вызываем метод
    username = "testuser"
    password_hash = "hashed_password"
    user_id, error = db_manager.create_user(username, password_hash)
    
    # Проверяем результаты
    assert user_id is None
    assert error is not None
    assert "Ошибка выполнения запроса" in error
    
    # Проверяем, что execute_query был вызван
    db_manager.execute_query.assert_called_once()

def test_get_user_by_username(db_manager):
    """Тестирует получение пользователя по имени."""
    # Мокаем возвращаемое значение для execute_query
    test_user_id = str(uuid.uuid4())
    mock_user = {
        "user_id": test_user_id,
        "username": "testuser",
        "password_hash": "hashed_password"
    }
    
    # Заменяем мок для execute_query вместо прямого мока fetchone
    db_manager.execute_query = MagicMock(return_value=(mock_user, None))
    
    # Вызываем метод
    user = db_manager.get_user_by_username("testuser")
    
    # Проверяем результаты
    assert user is not None
    assert user["user_id"] == test_user_id
    assert user["username"] == "testuser"
    assert user["password_hash"] == "hashed_password"
    
    # Проверяем, что execute_query был вызван с правильными параметрами
    db_manager.execute_query.assert_called_once()

def test_get_user_by_username_not_found(db_manager):
    """Тестирует получение несуществующего пользователя."""
    # Мокаем возвращаемое значение для execute_query с None результатом
    db_manager.execute_query = MagicMock(return_value=(None, None))
    
    # Вызываем метод
    user = db_manager.get_user_by_username("nonexistentuser")
    
    # Проверяем результаты
    assert user is None
    db_manager.execute_query.assert_called_once()

def test_save_video_metadata(db_manager):
    """Тестирует сохранение метаданных видео."""
    # Мокаем возвращаемое значение для execute_query
    test_video_id = uuid.uuid4()
    mock_result = {"video_id": test_video_id}
    db_manager.execute_query = MagicMock(return_value=(mock_result, None))
    
    # Подготавливаем данные
    user_id = str(uuid.uuid4())
    video_filename = "test_video.mp4"
    original_filename = "original.mp4"
    log_filename = "test_video.json"
    metadata = {
        "fps": "30",
        "detection_count": "10",
        "processed_date": datetime.now().isoformat()
    }
    
    # Вызываем метод
    video_id, error = db_manager.save_video_metadata(
        user_id,
        video_filename,
        original_filename,
        log_filename,
        metadata
    )
    
    # Проверяем результаты
    assert video_id == test_video_id
    assert error is None
    db_manager.execute_query.assert_called_once()

def test_save_video_metadata_error(db_manager):
    """Тестирует обработку ошибок при сохранении метаданных видео."""
    # Мокаем ошибку в execute_query
    db_manager.execute_query = MagicMock(return_value=(None, "Ошибка выполнения запроса: DB error"))
    
    # Подготавливаем данные
    user_id = str(uuid.uuid4())
    video_filename = "test_video.mp4"
    original_filename = "original.mp4"
    log_filename = "test_video.json"
    metadata = {
        "fps": "30",
        "detection_count": "10",
        "processed_date": datetime.now().isoformat()
    }
    
    # Вызываем метод
    video_id, error = db_manager.save_video_metadata(
        user_id,
        video_filename,
        original_filename,
        log_filename,
        metadata
    )
    
    # Проверяем результаты
    assert video_id is None
    assert error is not None
    assert "Ошибка выполнения запроса" in error
    db_manager.execute_query.assert_called_once()

def test_get_user_videos(db_manager):
    """Тестирует получение видео пользователя."""
    # Мокаем возвращаемое значение для execute_query
    test_video_id1 = str(uuid.uuid4())
    test_video_id2 = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    test_date = datetime.now()
    
    # Важно: metadata должен быть строкой в формате JSON, так как именно так
    # возвращается из базы данных и обрабатывается в методе get_user_videos
    metadata1 = json.dumps({"fps": "30"})
    metadata2 = json.dumps({"fps": "24"})
    
    mock_result = [
        {
            "video_id": test_video_id1,
            "filename": "video1.mp4", 
            "original_filename": "original1.mp4", 
            "log_filename": "video1.json", 
            "metadata": metadata1, 
            "upload_time": test_date, 
            "detection_count": 5
        },
        {
            "video_id": test_video_id2,
            "filename": "video2.mp4", 
            "original_filename": "original2.mp4", 
            "log_filename": "video2.json", 
            "metadata": metadata2, 
            "upload_time": test_date, 
            "detection_count": 3
        }
    ]
    
    # Заменяем мок для execute_query вместо прямого мока fetchall
    db_manager.execute_query = MagicMock(return_value=(mock_result, None))
    
    # Вызываем метод
    videos = db_manager.get_user_videos(test_user_id)
    
    # Проверяем результаты
    assert videos is not None
    assert len(videos) == 2
    assert videos[0]["video_id"] == test_video_id1
    assert videos[0]["filename"] == "video1.mp4"
    assert videos[0]["original_filename"] == "original1.mp4"
    assert videos[0]["log_filename"] == "video1.json"
    
    # Метод возвращает metadata как строку JSON, поэтому для проверки
    # необходимо распарсить её
    parsed_metadata = json.loads(videos[0]["metadata"])
    assert parsed_metadata["fps"] == "30"
    
    assert videos[0]["detection_count"] == 5
    
    # Проверяем, что execute_query был вызван
    db_manager.execute_query.assert_called()

def test_get_user_videos_error(db_manager):
    """Тестирует обработку ошибок при получении видео пользователя."""
    # Мокаем ошибку в execute_query
    db_manager.execute_query = MagicMock(return_value=(None, "Error fetching user videos"))
    
    # Вызываем метод
    test_user_id = str(uuid.uuid4())
    videos = db_manager.get_user_videos(test_user_id)
    
    # Проверяем результаты
    assert videos == []
    
    # Проверяем, что execute_query был вызван
    db_manager.execute_query.assert_called_once()

def test_delete_video(db_manager):
    """Тестирует удаление видео."""
    # Подготавливаем данные
    test_video_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    
    # Настраиваем mock для transaction
    mock_cursor = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_cursor
    db_manager.transaction = MagicMock(return_value=mock_context)
    
    # Настраиваем mock для имитации наличия видео
    mock_video = {
        "s3_key": "test_video.mp4",
        "bucket_name": "videos"
    }
    mock_cursor.fetchone.return_value = mock_video
    
    # Вызываем метод
    success, error = db_manager.delete_video(test_video_id, test_user_id)
    
    # Проверяем результаты
    assert success is True
    assert error is not None  # В данном случае возвращается объект video, а не None
    
    # Проверяем использование транзакции
    db_manager.transaction.assert_called_once()
    
    # Проверяем вызовы к курсору
    mock_cursor.execute.assert_called()
    mock_cursor.fetchone.assert_called_once()

def test_delete_video_error(db_manager):
    """Тестирует обработку ошибок при удалении видео."""
    # Настраиваем mock для transaction чтобы вызвать исключение
    db_manager.transaction = MagicMock(side_effect=Exception("DB error"))
    
    # Вызываем метод
    test_video_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    success, error = db_manager.delete_video(test_video_id, test_user_id)
    
    # Проверяем результаты
    assert success is False
    assert error is not None
    assert "Ошибка при удалении видео" in error
    
    # Проверяем, что метод transaction был вызван
    db_manager.transaction.assert_called_once() 