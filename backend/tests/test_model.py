import pytest
import os
import numpy as np
from unittest.mock import patch, MagicMock
import logging

# Инициализация логгера для тестов
logging.basicConfig(level=logging.INFO)

@pytest.fixture
def mock_yolo():
    """Мокирует класс YOLO и его экземпляр."""
    with patch('app.models.model.YOLO') as mock_yolo_class:
        # Создаем мок для экземпляра YOLO
        mock_model = MagicMock()
        mock_yolo_class.return_value = mock_model
        
        # Настраиваем метод predict
        mock_result = MagicMock()
        mock_result.boxes.cls = np.array([0, 1])  # Классы объектов
        mock_result.boxes.conf = np.array([0.8, 0.7])  # Уверенность
        mock_result.boxes.xyxy = np.array([
            [10, 10, 50, 50],
            [100, 100, 150, 150]
        ])  # Координаты bbox
        
        mock_model.predict.return_value = [mock_result]
        
        yield mock_model

def test_model_initialization():
    """Тестирует инициализацию модели YOLO."""
    # Необходимо импортировать модуль перед настройкой патчей
    import sys
    if 'app.models.model' in sys.modules:
        del sys.modules['app.models.model']
        
    # Устанавливаем патчи ПЕРЕД импортом модуля
    with patch('ultralytics.YOLO') as mock_yolo_class, \
         patch('os.path.exists') as mock_exists, \
         patch.dict(os.environ, {'MODEL_PATH': 'test_model.pt'}):
         
        # Задаем поведение мока - файл модели существует
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        mock_yolo_class.return_value = mock_model
        
        # Теперь импортируем модуль
        from app.models import model
        
        # Проверяем, что модель была успешно загружена
        assert model.model is not None
        


def test_model_prediction(mock_yolo):
    """Тестирует предсказание модели."""
    # Импортируем модуль с мокированной моделью
    with patch('app.models.model.model', mock_yolo):
        from app.models.model import model
        
        # Создаем тестовое изображение
        test_image = np.zeros((640, 480, 3), dtype=np.uint8)
        
        # Выполняем предсказание
        results = model.predict(test_image, conf=0.5)
        
        # Проверяем, что модель была вызвана
        model.predict.assert_called_once()
        
        # Проверяем, что аргумент был передан
        call_args = model.predict.call_args[0]
        assert call_args[0] is test_image
        
        # Проверяем результаты
        assert isinstance(results, list)
        assert len(results) == 1  # Должно быть одно предсказание
        
        # Проверяем свойства результата
        result = results[0]
        assert hasattr(result, 'boxes')
        assert hasattr(result.boxes, 'cls')
        assert hasattr(result.boxes, 'conf')
        assert hasattr(result.boxes, 'xyxy')

def test_model_prediction_with_parameters(mock_yolo):
    """Тестирует предсказание модели с различными параметрами."""
    # Импортируем модуль с мокированной моделью
    with patch('app.models.model.model', mock_yolo):
        from app.models.model import model
        
        # Создаем тестовое изображение
        test_image = np.zeros((640, 480, 3), dtype=np.uint8)
        
        # Выполняем предсказание с разными параметрами
        results = model.predict(
            test_image,
            conf=0.7,
            iou=0.5,
            classes=[0, 1, 2],
            agnostic_nms=True
        )
        
        # Проверяем, что модель была вызвана с правильными параметрами
        model.predict.assert_called_once()
        call_args, call_kwargs = model.predict.call_args
        
        # Проверяем позиционный аргумент (изображение)
        assert call_args[0] is test_image
        
        # Проверяем именованные аргументы
        assert call_kwargs.get('conf') == 0.7
        assert call_kwargs.get('iou') == 0.5
        assert call_kwargs.get('classes') == [0, 1, 2]
        assert call_kwargs.get('agnostic_nms') == True

def test_model_batch_prediction(mock_yolo):
    """Тестирует предсказание модели для батча изображений."""
    # Импортируем модуль с мокированной моделью
    with patch('app.models.model.model', mock_yolo):
        from app.models.model import model
        
        # Создаем батч из нескольких изображений
        batch_size = 3
        test_batch = [np.zeros((640, 480, 3), dtype=np.uint8) for _ in range(batch_size)]
        
        # Выполняем предсказание
        results = model.predict(test_batch, conf=0.5)
        
        # Проверяем, что модель была вызвана
        model.predict.assert_called_once()
        
        # Проверяем, что аргумент был передан
        call_args = model.predict.call_args[0]
        assert call_args[0] is test_batch
        
        # Проверяем результаты
        assert isinstance(results, list)
        assert len(results) == 1  # В нашем моке всегда 1 результат 