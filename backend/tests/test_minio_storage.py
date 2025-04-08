import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from app.services.minio.minio_storage import MinioStorage
from datetime import timedelta

@pytest.fixture
def mock_minio_client():
    """Фикстура для мокирования клиента MinIO"""
    with patch('app.services.minio.minio_storage.Minio') as mock_minio:
        # Настраиваем мок для bucket_exists
        mock_minio.return_value.bucket_exists.return_value = True
        yield mock_minio

@pytest.fixture
def storage(mock_minio_client):
    """Фикстура для создания экземпляра MinioStorage с мокированным клиентом"""
    storage = MinioStorage()
    storage.client = mock_minio_client.return_value
    return storage

def test_init_storage(storage, mock_minio_client):
    """Тестирует инициализацию хранилища MinIO."""
    # Проверяем, что клиент Minio был создан с правильными параметрами
    mock_minio_client.assert_called_with(
        endpoint=os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
        access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
        secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
        secure=os.environ.get('MINIO_SECURE', 'False').lower() == 'true',
        region=os.environ.get('MINIO_REGION', None)
    )

def test_save_video(storage):
    """Тестирует сохранение видео в MinIO."""
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(b"test video content")
        temp_path = temp_file.name

    try:
        # Вызываем метод сохранения видео
        metadata = {"test_key": "test_value"}
        result = storage.save_video(temp_path, "test_video.mp4", metadata=metadata)

        # Проверяем результат
        assert result is True

        # Проверяем, что был вызван fput_object с правильными параметрами
        storage.client.fput_object.assert_called_once_with(
            bucket_name=storage.video_bucket,
            object_name="test_video.mp4",
            file_path=temp_path,
            content_type='video/mp4',
            metadata=metadata
        )
    finally:
        # Удаляем временный файл
        os.unlink(temp_path)

def test_save_log(storage):
    """Тестирует сохранение логов в MinIO."""
    # Подготавливаем тестовые данные
    log_data = [
        [0, 0.8, 10, 10, 50, 50, "person"],
        [1, 0.7, 100, 100, 150, 150, "car"]
    ]

    # Вызываем метод сохранения логов
    metadata = {"video_id": "test123"}
    result = storage.save_log(log_data, "test_log.json", metadata=metadata)

    # Проверяем результат
    assert result is True

    # Проверяем, что был вызван put_object с правильными параметрами
    storage.client.put_object.assert_called_once()
    call_args = storage.client.put_object.call_args[1]
    assert call_args['bucket_name'] == storage.log_bucket
    assert call_args['object_name'] == 'test_log.json'
    assert call_args['content_type'] == 'application/json'
    assert call_args['metadata'] == metadata
    
    # Проверяем содержимое данных
    data_io = call_args['data']
    data_io.seek(0)  # Возвращаем указатель в начало
    data = json.loads(data_io.read().decode('utf-8'))
    assert data == log_data

def test_get_presigned_url(storage):
    """Тестирует получение предподписанного URL."""
    # Настраиваем мок для presigned_get_object
    storage.client.presigned_get_object.return_value = "http://example.com/test_video.mp4"
    
    # Настраиваем мок для stat_object, чтобы проверка существования объекта прошла успешно
    storage.client.stat_object.return_value = True

    # Вызываем метод получения URL
    url = storage.get_presigned_url("test_video.mp4", expires=3600)

    # Проверяем результат
    assert url == "http://example.com/test_video.mp4"

    # Проверяем, что был вызван stat_object для проверки существования объекта
    storage.client.stat_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='test_video.mp4'
    )

    # Проверяем, что был вызван presigned_get_object с правильными параметрами
    storage.client.presigned_get_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='test_video.mp4',
        expires=timedelta(seconds=3600)
    )

def test_get_log(storage):
    """Тестирует получение файла логов."""
    # Подготавливаем тестовые данные
    log_data = [
        [0, 0.8, 10, 10, 50, 50, "person"],
        [1, 0.7, 100, 100, 150, 150, "car"]
    ]
    log_json = json.dumps(log_data).encode('utf-8')

    # Мокаем response от get_object
    mock_response = MagicMock()
    mock_response.read.return_value = log_json
    mock_response.__enter__.return_value = mock_response
    storage.client.get_object.return_value = mock_response

    # Вызываем метод получения логов
    result = storage.get_log("test_log.json")

    # Проверяем результат
    assert result == log_data

    # Проверяем, что был вызван get_object с правильными параметрами
    storage.client.get_object.assert_called_once_with(
        bucket_name=storage.log_bucket,
        object_name='test_log.json'
    )

def test_delete_objects(storage):
    """Тестирует удаление объектов."""
    # Вызываем метод удаления объектов
    result = storage.delete_objects("test_video.mp4", "test_log.json")

    # Проверяем результат
    assert result is True

    # Проверяем, что был вызван remove_object для видео и логов
    assert storage.client.remove_object.call_count == 2

    # Проверяем аргументы вызова для видео
    video_call = storage.client.remove_object.call_args_list[0]
    assert video_call[1]['bucket_name'] == storage.video_bucket
    assert video_call[1]['object_name'] == 'test_video.mp4'

    # Проверяем аргументы вызова для логов
    log_call = storage.client.remove_object.call_args_list[1]
    assert log_call[1]['bucket_name'] == storage.log_bucket
    assert log_call[1]['object_name'] == 'test_log.json'

def test_rename_object(storage):
    """Тестирует переименование объекта."""
    # Вызываем метод переименования
    result = storage.rename_object(storage.video_bucket, 'old_name.mp4', 'new_name.mp4')

    # Проверяем результат
    assert result is True

    # Проверяем вызовы методов с правильными параметрами
    storage.client.copy_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='new_name.mp4',
        source_bucket_name=storage.video_bucket,
        source_object_name='old_name.mp4'
    )
    storage.client.remove_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='old_name.mp4'
    )

def test_error_handling_save_video(storage):
    """Тестирует обработку ошибок при сохранении видео."""
    # Мокаем исключение при вызове fput_object
    storage.client.fput_object.side_effect = Exception("Minio error")

    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(b"test video content")
        temp_path = temp_file.name

    try:
        # Вызываем метод сохранения видео и проверяем, что исключение обрабатывается
        result = storage.save_video(temp_path, "test_video.mp4")
        assert result is False
    finally:
        # Удаляем временный файл
        os.unlink(temp_path)

def test_error_handling_get_log(storage):
    """Тестирует обработку ошибок при получении логов."""
    # Мокаем исключение при вызове get_object
    storage.client.get_object.side_effect = Exception("Minio error")

    # Вызываем метод получения логов и проверяем, что исключение обрабатывается
    result = storage.get_log("test_log.json")
    assert result is None 