import pytest
import os
import json
import tempfile
import cv2
import numpy as np
from unittest.mock import patch, MagicMock, mock_open
from app.services.video_processing import video_processing


@pytest.fixture
def mock_video_file():
    """Создает временный видеофайл для тестирования."""
    # Создаем временный файл
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    temp_file.close()
    
    # Создаем тестовое видео с помощью OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30
    frame_size = (640, 480)
    writer = cv2.VideoWriter(temp_file.name, fourcc, fps, frame_size)
    
    # Создаем несколько кадров
    for _ in range(5):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Рисуем прямоугольник для тестирования детекции
        cv2.rectangle(frame, (100, 100), (200, 200), (0, 255, 0), -1)
        writer.write(frame)
    
    writer.release()
    
    yield temp_file.name
    
    # Удаляем временный файл после тестов
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)

@pytest.fixture
def mock_yolo():
    """Мокирует модель YOLO для тестирования."""
    with patch('app.models.model.model') as mock_model:
        # Настраиваем мок для имитации результатов детекции
        mock_result = MagicMock()
        mock_result.boxes.cls = np.array([0, 1])  # Классы объектов
        mock_result.boxes.conf = np.array([0.8, 0.7])  # Уверенность
        mock_result.boxes.xyxy = np.array([
            [10, 10, 50, 50],
            [100, 100, 150, 150]
        ])  # Координаты bbox
        
        # Настраиваем вывод батчей результатов
        mock_model.predict.return_value = [mock_result]
        
        yield mock_model

@pytest.fixture
def mock_storage():
    """Мокирует хранилище MinIO для тестирования."""
    with patch('app.services.video_processing.video_processing.MinioStorage') as mock_minio_class:
        mock_storage = MagicMock()
        mock_minio_class.return_value = mock_storage
        
        # Настраиваем методы хранилища
        mock_storage.save_video.return_value = True
        mock_storage.save_log.return_value = True
        
        yield mock_storage

def test_process_video_invalid_file(mock_storage):
    """Тестирует обработку недопустимого видеофайла."""
    # Создаем невалидный файл
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        temp_file.write(b"This is not a video file")
        temp_path = temp_file.name
    
    try:
        # Патчим VideoCapture, чтобы он возвращал ложь при isOpened()
        with patch('app.services.video_processing.video_processing.cv2.VideoCapture') as mock_cap:
            mock_cap_instance = MagicMock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = False
            
            # Вызываем тестируемый метод
            with pytest.raises(ValueError) as excinfo:
                video_processing.process_video(
                    temp_path,
                    0.6,
                    "testuser"
                )
            
            # Проверяем сообщение об ошибке
            assert "не удалось открыть" in str(excinfo.value).lower()
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.remove(temp_path) 