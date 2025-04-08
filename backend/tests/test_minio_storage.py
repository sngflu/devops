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
    mock_minio_client.assert_called_with(
        endpoint=os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
        access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
        secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
        secure=os.environ.get('MINIO_SECURE', 'False').lower() == 'true',
        region=os.environ.get('MINIO_REGION', None)
    )

def test_save_video(storage):
    """Тестирует сохранение видео в MinIO."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(b"test video content")
        temp_path = temp_file.name

    try:
        metadata = {"test_key": "test_value"}
        result = storage.save_video(temp_path, "test_video.mp4", metadata=metadata)

        assert result is True

        
        storage.client.fput_object.assert_called_once_with(
            bucket_name=storage.video_bucket,
            object_name="test_video.mp4",
            file_path=temp_path,
            content_type='video/mp4',
            metadata=metadata
        )
    finally:
        os.unlink(temp_path)

def test_save_log(storage):
    """Тестирует сохранение логов в MinIO."""
    log_data = [
        [0, 0.8, 10, 10, 50, 50, "person"],
        [1, 0.7, 100, 100, 150, 150, "car"]
    ]

    metadata = {"video_id": "test123"}
    result = storage.save_log(log_data, "test_log.json", metadata=metadata)

    assert result is True

    
    storage.client.put_object.assert_called_once()
    call_args = storage.client.put_object.call_args[1]
    assert call_args['bucket_name'] == storage.log_bucket
    assert call_args['object_name'] == 'test_log.json'
    assert call_args['content_type'] == 'application/json'
    assert call_args['metadata'] == metadata
    
    data_io = call_args['data']
    data_io.seek(0)
    data = json.loads(data_io.read().decode('utf-8'))
    assert data == log_data

def test_get_presigned_url(storage):
    """Тестирует получение предподписанного URL."""
    storage.client.presigned_get_object.return_value = "http://example.com/test_video.mp4"
    
    storage.client.stat_object.return_value = True

    url = storage.get_presigned_url("test_video.mp4", expires=7)

    assert url == "http://example.com/test_video.mp4"

    storage.client.stat_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='test_video.mp4'
    )

    storage.client.presigned_get_object.assert_called_once_with(
        bucket_name=storage.video_bucket,
        object_name='test_video.mp4',
        expires=timedelta(days=7)
    )

def test_get_log(storage):
    """Тестирует получение файла логов."""
    log_data = [
        [0, 0.8, 10, 10, 50, 50, "person"],
        [1, 0.7, 100, 100, 150, 150, "car"]
    ]
    log_json = json.dumps(log_data).encode('utf-8')

    mock_response = MagicMock()
    mock_response.read.return_value = log_json
    mock_response.__enter__.return_value = mock_response
    storage.client.get_object.return_value = mock_response

    result = storage.get_log("test_log.json")

    assert result == log_data

    storage.client.get_object.assert_called_once_with(
        bucket_name=storage.log_bucket,
        object_name='test_log.json'
    )

def test_delete_objects(storage):
    """Тестирует удаление объектов."""
    result = storage.delete_objects("test_video.mp4", "test_log.json")

    assert result is True

    
    assert storage.client.remove_object.call_count == 2

    
    video_call = storage.client.remove_object.call_args_list[0]
    assert video_call[1]['bucket_name'] == storage.video_bucket
    assert video_call[1]['object_name'] == 'test_video.mp4'

    
    log_call = storage.client.remove_object.call_args_list[1]
    assert log_call[1]['bucket_name'] == storage.log_bucket
    assert log_call[1]['object_name'] == 'test_log.json'

def test_rename_object(storage):
    """Тестирует переименование объекта."""
    result = storage.rename_object(storage.video_bucket, 'old_name.mp4', 'new_name.mp4')

    assert result is True

    
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
    storage.client.fput_object.side_effect = Exception("Minio error")

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(b"test video content")
        temp_path = temp_file.name

    try:
        result = storage.save_video(temp_path, "test_video.mp4")
        assert result is False
    finally:
        os.unlink(temp_path)

def test_error_handling_get_log(storage):
    """Тестирует обработку ошибок при получении логов."""
    storage.client.get_object.side_effect = Exception("Minio error")

    result = storage.get_log("test_log.json")
    assert result is None 