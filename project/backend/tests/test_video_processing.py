import pytest
import os
import json
import tempfile
import cv2
import numpy as np
from unittest.mock import patch, MagicMock, mock_open, ANY
from app.services.video_processing import video_processing


@pytest.fixture
def mock_ffmpeg():
    """Мокирует moviepy для тестирования."""
    with patch("moviepy.editor.VideoFileClip") as mock_video:
        mock_video_instance = MagicMock()
        mock_video.return_value = mock_video_instance
        mock_video_instance.write_videofile.return_value = None
        yield mock_video


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
        writer.write(frame)

    writer.release()

    yield temp_file.name

    # Удаляем временный файл после тестов
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


@pytest.fixture
def mock_storage():
    """Мокирует хранилище MinIO для тестирования."""
    with patch(
        "app.services.video_processing.video_processing.storage"
    ) as mock_storage:
        mock_storage.save_video.return_value = True
        mock_storage.save_log.return_value = True
        mock_storage.client = MagicMock()
        yield mock_storage


@pytest.fixture
def mock_model():
    """Мокирует модель YOLO для тестирования."""
    with patch("app.services.video_processing.video_processing.model") as mock_model:
        mock_result = MagicMock()
        mock_result.boxes.cls = np.array([0, 1])
        mock_result.boxes.conf = np.array([0.8, 0.7])
        mock_result.boxes.xyxy = np.array([[10, 10, 50, 50], [100, 100, 150, 150]])
        mock_result.names = {0: "weapon", 1: "knife"}
        mock_model.model.return_value = [mock_result]
        yield mock_model


@pytest.fixture
def mock_video_capture():
    """Мокирует cv2.VideoCapture для тестирования."""
    with patch("cv2.VideoCapture") as mock_cap:
        mock_cap_instance = MagicMock()
        mock_cap.return_value = mock_cap_instance
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: 30,
            cv2.CAP_PROP_FPS: 30,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)
        yield mock_cap


def test_process_video_success(
    mock_video_capture, mock_model, mock_storage, mock_video_file
):
    """Тест успешной обработки видео."""
    # Проверяем успешную обработку
    result = video_processing.process_video(
        mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
    )
    assert isinstance(result, tuple)
    assert len(result) == 5
    assert result[0].endswith(".mp4")
    assert isinstance(result[1], list)
    assert isinstance(result[2], int)
    assert isinstance(result[3], bool)
    assert result[4].endswith(".json")


def test_process_video_invalid_file(mock_storage):
    """Тест обработки недопустимого видеофайла."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(b"This is not a video file")
        temp_path = temp_file.name

    try:
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap_instance = MagicMock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = False

            with pytest.raises(ValueError) as excinfo:
                video_processing.process_video(temp_path, 0.25, "testuser")

            assert "не удалось открыть" in str(excinfo.value).lower()
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_process_video_file_not_found(mock_storage):
    """Тест обработки отсутствующего файла."""
    with pytest.raises(FileNotFoundError):
        video_processing.process_video("nonexistent.mp4", 0.25, "testuser")


def test_process_video_no_detections(
    mock_video_capture, mock_model, mock_storage, mock_video_file
):
    """Тест обработки видео без обнаруженных объектов."""
    # Настраиваем мок модели для возврата пустого результата
    mock_model.model.return_value = [MagicMock(boxes=[])]

    # Проверяем успешную обработку без обнаружений
    result = video_processing.process_video(
        mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
    )
    assert isinstance(result, tuple)
    assert len(result) == 5
    assert result[0].endswith(".mp4")
    assert isinstance(result[1], list)
    assert isinstance(result[2], int)
    assert isinstance(result[3], bool)
    assert result[4].endswith(".json")


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


def test_process_video_mp4_output(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки видео с выходом в формате MP4."""
    # Настраиваем мок moviepy для успешной обработки
    mock_ffmpeg.return_value.write_videofile.return_value = None

    # Проверяем, что функция возвращает кортеж для успешной обработки
    result = video_processing.process_video(
        mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
    )
    assert isinstance(result, tuple)
    assert len(result) == 5
    assert result[0].endswith(".mp4")
    assert isinstance(result[1], list)
    assert isinstance(result[2], int)
    assert isinstance(result[3], bool)
    assert result[4].endswith(".json")


def test_process_video_avi_output(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки видео с выходом в формате AVI."""
    # Настраиваем мок moviepy для успешной обработки
    mock_ffmpeg.return_value.write_videofile.return_value = None

    # Проверяем, что функция возвращает кортеж для успешной обработки
    result = video_processing.process_video(
        mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
    )
    assert isinstance(result, tuple)
    assert len(result) == 5
    assert result[0].endswith(".mp4")
    assert isinstance(result[1], list)
    assert isinstance(result[2], int)
    assert isinstance(result[3], bool)
    assert result[4].endswith(".json")


def test_process_video_no_output_files(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки видео без выходных файлов."""
    # Настраиваем мок moviepy для имитации отсутствия выходных файлов
    mock_ffmpeg.return_value.write_videofile.side_effect = Exception(
        "No output files generated"
    )

    # Проверяем, что функция возвращает кортеж при отсутствии выходных файлов
    result = video_processing.process_video(
        mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
    )
    assert isinstance(result, tuple)
    assert len(result) == 5
    assert result[0].endswith(".mp4")
    assert isinstance(result[1], list)
    assert isinstance(result[2], int)
    assert isinstance(result[3], bool)
    assert result[4].endswith(".json")


def test_process_video_zero_size_file(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки видео с нулевым размером файла."""
    # Настраиваем мок для имитации нулевого размера файла
    with patch("os.path.getsize", return_value=0):
        # Настраиваем мок moviepy для успешной обработки
        mock_ffmpeg.return_value.write_videofile.return_value = None

        # Проверяем, что функция возвращает кортеж для файла нулевого размера
        result = video_processing.process_video(
            mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
        )
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result[0].endswith(".mp4")
        assert isinstance(result[1], list)
        assert isinstance(result[2], int)
        assert isinstance(result[3], bool)
        assert result[4].endswith(".json")


def test_process_video_missing_directory(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки видео с отсутствующей директорией."""
    # Настраиваем мок для имитации отсутствия директории
    with patch("os.makedirs", side_effect=OSError("Permission denied")):
        # Настраиваем мок moviepy для успешной обработки
        mock_ffmpeg.return_value.write_videofile.return_value = None

        # Проверяем, что функция возвращает кортеж при отсутствии директории
        result = video_processing.process_video(
            mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
        )
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result[0].endswith(".mp4")
        assert isinstance(result[1], list)
        assert isinstance(result[2], int)
        assert isinstance(result[3], bool)
        assert result[4].endswith(".json")


def test_process_video_cleanup_error(
    mock_storage, mock_ffmpeg, mock_model, mock_video_file
):
    """Тест обработки ошибки при очистке временных файлов."""
    # Настраиваем мок для имитации ошибки при удалении файла
    with patch("os.unlink", side_effect=OSError("Permission denied")):
        # Настраиваем мок moviepy для успешной обработки
        mock_ffmpeg.return_value.write_videofile.return_value = None

        # Проверяем, что функция возвращает кортеж при ошибке очистки
        result = video_processing.process_video(
            mock_video_file, 0.25, "testuser"  # confidence_threshold  # username
        )
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result[0].endswith(".mp4")
        assert isinstance(result[1], list)
        assert isinstance(result[2], int)
        assert isinstance(result[3], bool)
        assert result[4].endswith(".json")
