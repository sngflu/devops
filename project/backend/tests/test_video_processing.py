import pytest
import os
import json
import tempfile
import cv2
import numpy as np
from unittest.mock import patch, MagicMock, mock_open, ANY
from app.services.video_processing import video_processing


@pytest.fixture
def mock_video_file():
    """Создает временный видеофайл для тестирования."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    temp_file.close()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 30
    frame_size = (640, 480)
    writer = cv2.VideoWriter(temp_file.name, fourcc, fps, frame_size)

    for _ in range(5):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (100, 100), (200, 200), (0, 255, 0), -1)
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
    with patch("app.models.model.model") as mock_model:
        mock_result = MagicMock()
        mock_result.boxes.cls = np.array([0, 1])
        mock_result.boxes.conf = np.array([0.8, 0.7])
        mock_result.boxes.xyxy = np.array([[10, 10, 50, 50], [100, 100, 150, 150]])

        # Mock predict to return a list containing the mock result (for non-streamed use if any)
        mock_model.predict.return_value = [mock_result]

        yield mock_model


@pytest.fixture
def mock_storage():
    """Мокирует хранилище MinIO для тестирования."""
    with patch(
        "app.services.video_processing.video_processing.MinioStorage"
    ) as mock_minio_class:
        mock_storage = MagicMock()
        mock_minio_class.return_value = mock_storage

        mock_storage.save_video.return_value = True
        mock_storage.save_log.return_value = True

        yield mock_storage


def test_process_video_invalid_file(mock_storage):
    """Тестирует обработку недопустимого видеофайла."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(b"This is not a video file")
        temp_path = temp_file.name

    try:
        with patch(
            "app.services.video_processing.video_processing.cv2.VideoCapture"
        ) as mock_cap:
            mock_cap_instance = MagicMock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = False

            with pytest.raises(ValueError) as excinfo:
                video_processing.process_video(temp_path, 0.6, "testuser")

            assert "не удалось открыть" in str(excinfo.value).lower()
    finally:

        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.fixture
def sample_video():
    """Создает временный тестовый видеофайл."""
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as tmp:
        # Создаем простое видео с помощью OpenCV
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(tmp.name, fourcc, 20.0, (640, 480))
        for _ in range(30):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def mock_model_iterable():
    """Мокирует модель YOLO для возврата списка итератора результатов."""
    with patch("app.models.model.model") as mock:
        mock_frame_results = []
        for i in range(3):
            frame_result = MagicMock()
            frame_result.names = {0: "weapon", 1: "knife"}
            if i == 0:
                box = MagicMock()
                box.cls = [0]  # weapon class
                box.conf = [0.8]
                box.xyxy = [[10, 10, 50, 50]]
                frame_result.boxes = [box]
            elif i == 1:
                box = MagicMock()
                box.cls = [1]  # knife class
                box.conf = [0.7]
                box.xyxy = [[100, 100, 150, 150]]
                frame_result.boxes = [box]
            else:
                frame_result.boxes = []
            mock_frame_results.append(frame_result)

        # Возвращаем список мок-результатов, а не итератор напрямую
        mock.return_value = mock_frame_results
        yield mock


def test_convert_avi_to_mp4_success(sample_video):
    """Тестирует успешную конвертацию AVI в MP4."""
    output_file = sample_video.replace(".avi", ".mp4")
    try:
        result = video_processing.convert_avi_to_mp4(sample_video, output_file)
        assert result is True
        assert os.path.exists(output_file)
    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)


def test_convert_avi_to_mp4_file_not_found():
    """Тестирует обработку ошибки при отсутствии файла."""
    result = video_processing.convert_avi_to_mp4("nonexistent.avi", "output.mp4")
    assert result is False


def test_process_video_file_not_found():
    """Тестирует обработку ошибки при отсутствии файла."""
    with pytest.raises(FileNotFoundError):
        video_processing.process_video("nonexistent.mp4", username="testuser")


def test_process_video_invalid_format():
    """Тестирует обработку ошибки при неверном формате файла."""
    with patch("os.path.exists", return_value=True), patch(
        "cv2.VideoCapture"
    ) as mock_cap:

        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = False

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        with pytest.raises(ValueError, match="Не удалось открыть видеофайл"):
            video_processing.process_video("invalid.mp4", username="testuser")


def test_process_video_mp4_output(sample_video, mock_model_iterable):
    """Тестирует обработку видео с MP4 выходом."""
    with patch("os.path.exists", return_value=True), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "os.path.getsize", return_value=1024
    ), patch(
        "tempfile.gettempdir", return_value="/tmp"
    ), patch(
        "os.path.join", side_effect=lambda *args: "runs/detect/predict/test.mp4"
    ), patch(
        "os.remove"
    ):
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        result = video_processing.process_video(sample_video, username="testuser")
        assert result is not None
        mock_copy.assert_called()  # Проверяем, что произошло копирование


def test_process_video_avi_output(sample_video, mock_model_iterable):
    """Тестирует обработку видео с AVI выходом."""
    with patch("os.path.exists", side_effect=lambda x: x.endswith(".avi")), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "app.services.video_processing.video_processing.convert_avi_to_mp4",
        return_value=True,
    ):
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        result = video_processing.process_video(sample_video, username="testuser")
        assert result is not None


def test_process_video_no_output_files(sample_video, mock_model_iterable):
    """Тестирует обработку видео без выходных файлов."""
    with patch("os.path.exists", side_effect=lambda x: x == sample_video), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "os.path.getsize", return_value=1024
    ), patch(
        "tempfile.gettempdir", return_value="/tmp"
    ), patch(
        "os.path.join", side_effect=lambda *args: "/tmp/test.mp4"
    ), patch(
        "os.listdir", return_value=[]
    ), patch(
        "os.remove"
    ):
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        result = video_processing.process_video(sample_video, username="testuser")
        assert result is not None
        mock_copy.assert_called_with(
            sample_video, ANY
        )  # Проверяем копирование оригинала


def test_process_video_zero_size_file(sample_video, mock_model_iterable):
    """Тестирует обработку видео с нулевым размером файла."""
    with patch("os.path.exists", return_value=True), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "os.path.getsize", return_value=0
    ), patch(
        "tempfile.gettempdir", return_value="/tmp"
    ), patch(
        "os.path.join", side_effect=lambda *args: "/tmp/test.mp4"
    ), patch(
        "os.remove"
    ):
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        result = video_processing.process_video(sample_video, username="testuser")
        assert result is not None
        # Проверяем, что был создан пустой результат
        mock_copy.assert_called_with(sample_video, ANY)


def test_process_video_missing_directory(sample_video, mock_model_iterable):
    """Тестирует обработку видео при отсутствии директории для результатов."""
    with patch("os.path.exists", side_effect=lambda x: x == sample_video), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "os.path.getsize", return_value=1024
    ), patch(
        "tempfile.gettempdir", return_value="/tmp"
    ), patch(
        "os.path.join", side_effect=lambda *args: "runs/detect/predict/test.mp4"
    ), patch(
        "os.listdir", return_value=[]
    ), patch(
        "os.remove"
    ), patch(
        "os.makedirs"
    ) as mock_makedirs:
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        result = video_processing.process_video(sample_video, username="testuser")
        assert result is not None
        # Проверяем, что была создана директория
        mock_makedirs.assert_called_with(
            "runs/detect/predict/", exist_ok=True
        )  # Updated path with trailing slash
        # Проверяем, что был скопирован оригинал
        mock_copy.assert_called_with(sample_video, ANY)


def test_process_video_cleanup_error(sample_video, mock_model_iterable):
    """Тестирует обработку ошибок при очистке временных файлов."""
    with patch("os.path.exists", return_value=True), patch(
        "cv2.VideoCapture"
    ) as mock_cap, patch("shutil.copy2") as mock_copy, patch(
        "os.path.getsize", return_value=1024
    ), patch(
        "tempfile.gettempdir", return_value="/tmp"
    ), patch(
        "os.path.join", side_effect=lambda *args: "/tmp/test.mp4"
    ), patch(
        "os.remove", side_effect=OSError("Permission denied")
    ), patch(
        "shutil.rmtree", side_effect=OSError("Permission denied")
    ), patch(
        "app.services.video_processing.video_processing.logger"
    ) as mock_logger:
        # Настраиваем мок VideoCapture
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True

        def mock_get(prop):
            props = {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 20,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }
            return props.get(prop, 0)

        mock_cap_instance.get.side_effect = mock_get

        # Настраиваем моки grab() и retrieve()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.grab.side_effect = [True] * 30 + [False]
        mock_cap_instance.retrieve.side_effect = [(True, fake_frame)] * 30 + [
            (False, None)
        ]

        # Ожидаем, что будет выброшено OSError
        with pytest.raises(OSError) as exc_info:
            video_processing.process_video(sample_video, username="testuser")

        # Проверяем текст ошибки
        assert "Permission denied" in str(exc_info.value)

        # Проверяем, что было вызвано логирование ошибки очистки
        # Эти логи должны быть вызваны перед тем, как outer except перехватит и пробросит ошибку
        mock_logger.warning.assert_called_with(ANY)
        # Проверяем, что был вызван error с сообщением об ошибке очистки
        mock_logger.error.assert_called_with(
            ANY
        )  # Проверяем, что был вызван error с любым аргументом
