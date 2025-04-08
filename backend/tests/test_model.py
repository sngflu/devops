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
        
        yield mock_model

def test_model_initialization():
    """Тестирует инициализацию модели YOLO."""
    import sys
    if 'app.models.model' in sys.modules:
        del sys.modules['app.models.model']
        
    with patch('ultralytics.YOLO') as mock_yolo_class, \
         patch('os.path.exists') as mock_exists, \
         patch.dict(os.environ, {'MODEL_PATH': 'test_model.pt'}):
         
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        mock_yolo_class.return_value = mock_model
        
        from app.models import model
        
        assert model.model is not None
        


def test_model_prediction(mock_yolo):
    """Тестирует предсказание модели."""
    with patch('app.models.model.model', mock_yolo):
        from app.models.model import model
        
        test_image = np.zeros((640, 480, 3), dtype=np.uint8)
        
        results = model.predict(test_image, conf=0.5)
        
        model.predict.assert_called_once()
        
        call_args = model.predict.call_args[0]
        assert call_args[0] is test_image
        
        assert isinstance(results, list)
        assert len(results) == 1
        
        result = results[0]
        assert hasattr(result, 'boxes')
        assert hasattr(result.boxes, 'cls')
        assert hasattr(result.boxes, 'conf')
        assert hasattr(result.boxes, 'xyxy')

