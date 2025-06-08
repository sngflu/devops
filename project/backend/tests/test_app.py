import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from app import create_app
from app.services.minio import MinioStorage
import jwt


@pytest.fixture
def app():
    """Создает и настраивает экземпляр Flask для тестирования."""
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})

    yield app


@pytest.fixture
def client(app):
    """Создает тестовый клиент для приложения."""
    return app.test_client()


def test_app_works(client):
    """Проверяет, что приложение запускается и отвечает на запросы."""
    response = client.get("/health")
    assert response.status_code == 200


def test_login_route_exists(client):
    """Проверяет, что маршрут /login существует и принимает POST запросы."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.return_value = {
        "user_id": 1,
        "username": "testuser",
        "password_hash": "hashed_password",
    }

    with patch("app.api.routes.db_manager", mock_db_manager), patch(
        "app.api.routes.check_password_hash", return_value=True
    ):
        response = client.post(
            "/login", json={"username": "testuser", "password": "testpassword"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data


# New tests for /register route error cases
def test_register_missing_fields(client):
    """Тестирует регистрацию без обязательных полей."""
    response = client.post("/register", json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "Username and password are required" in data["message"]


def test_register_user_exists(client):
    """Тестирует регистрацию существующего пользователя."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.return_value = {"username": "testuser"}
    with patch("app.api.routes.db_manager", mock_db_manager):
        response = client.post(
            "/register", json={"username": "testuser", "password": "testpassword"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Username already exists" in data["message"]


def test_register_db_error(client):
    """Тестирует ошибку БД при регистрации."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.return_value = None
    mock_db_manager.create_user.return_value = (
        None,
        "Some DB Error",
    )  # Use a simple string
    with patch("app.api.routes.db_manager", mock_db_manager):
        response = client.post(
            "/register", json={"username": "testuser", "password": "testpassword"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Some DB Error" in data["message"]


def test_register_exception(client):
    """Тестирует непредвиденное исключение при регистрации."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.side_effect = Exception("Unexpected Error")
    with patch("app.api.routes.db_manager", mock_db_manager):
        response = client.post(
            "/register", json={"username": "testuser", "password": "testpassword"}
        )
        assert response.status_code == 500


# New tests for /login route error cases
def test_login_missing_fields(client):
    """Тестирует логин без обязательных полей."""
    response = client.post("/login", json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "Username and password are required" in data["message"]


def test_login_invalid_credentials(client):
    """Тестирует логин с неверными учетными данными."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.return_value = {
        "user_id": 1,
        "username": "testuser",
        "password_hash": "hashed_password",
    }
    with patch("app.api.routes.db_manager", mock_db_manager), patch(
        "app.api.routes.check_password_hash", return_value=False
    ):
        response = client.post(
            "/login", json={"username": "testuser", "password": "wrong_password"}
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "Invalid credentials" in data["message"]


def test_login_exception(client):
    """Тестирует непредвиденное исключение при логине."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.side_effect = Exception("Unexpected Error")
    with patch("app.api.routes.db_manager", mock_db_manager):
        response = client.post(
            "/login", json={"username": "testuser", "password": "testpassword"}
        )
        assert response.status_code == 500


# New tests for token_required decorator
def test_token_required_missing_token(client):
    """Тестирует доступ к защищенному маршруту без токена."""
    # Предполагаем, что есть защищенный маршрут, например /videos
    response = client.get("/videos")
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Token is missing" in data["message"]


def test_token_required_invalid_token(client):
    """Тестирует доступ к защищенному маршруту с невалидным токеном."""
    # Предполагаем, что есть защищенный маршрут, например /videos
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/videos", headers=headers)
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Invalid token" in data["message"]


@pytest.fixture
def mock_minio_storage():
    with patch("app.services.minio.MinioStorage") as mock_storage:
        mock_instance = MagicMock()
        mock_storage.return_value = mock_instance

        mock_instance.save_video.return_value = True
        mock_instance.save_log.return_value = True
        mock_instance.get_presigned_url.return_value = (
            "https://minio.example.com/videos/test_video.mp4"
        )
        mock_instance.get_log.return_value = [(0, 1, 0), (1, 0, 1)]
        mock_instance.list_user_videos.return_value = [
            {
                "filename": "test_user_20230101_video.mp4",
                "original_name": "video.mp4",
                "log_count": 2,
            }
        ]
        mock_instance.delete_objects.return_value = True
        mock_instance.rename_object.return_value = True

        yield mock_instance


@pytest.fixture
def authenticated_client(client):
    """Создает аутентифицированный клиент для тестирования защищенных маршрутов."""
    mock_db_manager = MagicMock()
    mock_db_manager.get_user_by_username.return_value = {
        "user_id": 1,
        "username": "testuser",
        "password_hash": "hashed_password",
    }

    with patch("app.api.routes.db_manager", mock_db_manager), patch(
        "app.api.routes.check_password_hash", return_value=True
    ):
        # Регистрация
        client.post(
            "/register", json={"username": "testuser", "password": "testpassword"}
        )

        # Логин
        response = client.post(
            "/login", json={"username": "testuser", "password": "testpassword"}
        )
        token = json.loads(response.data)["token"]

        client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return client


def test_video_upload_to_minio(authenticated_client, test_video_file):
    """Проверяет загрузку видео в MinIO."""
    with patch("app.api.routes.video_processing.process_video") as mock_process:
        mock_process.return_value = (
            "testuser_20230101_video.mp4",  # video_filename
            [[0, 0.8, "person"], [1, 0.7, "car"]],  # frame_objects
            30,  # fps
            False,  # has_weapon
            "testuser_20230101_video.json",  # log_filename
        )
        with open(test_video_file, "rb") as video_file:
            response = authenticated_client.post(
                "/predict",
                data={"file": (video_file, "test_video.mp4")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "video_url" in data
        assert "frame_objects" in data
        assert "fps" in data


def test_get_video_from_minio(authenticated_client):
    """Проверяет получение видео из MinIO."""
    with patch(
        "app.api.routes.storage.get_presigned_url",
        return_value="https://example.com/video.mp4",
    ):
        response = authenticated_client.get("/video/testuser_video.mp4")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "url" in data
        assert data["url"] == "https://example.com/video.mp4"


def test_delete_video_from_minio(authenticated_client):
    """Проверяет удаление видео из MinIO."""
    with patch("app.api.routes.storage.delete_objects", return_value=True):
        response = authenticated_client.delete("/videos/testuser_video.mp4")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["message"] == "Successfully deleted"


# New tests for /predict route error scenarios
def test_predict_no_file(authenticated_client):
    """Тестирует загрузку без файла."""
    response = authenticated_client.post("/predict", data={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "No file part" in data["error"]


def test_predict_empty_filename(authenticated_client, test_video_file):
    """Тестирует загрузку с пустым именем файла."""
    with open(test_video_file, "rb") as video_file:
        response = authenticated_client.post(
            "/predict",
            data={"file": (video_file, "")},
            content_type="multipart/form-data",
        )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "No selected file" in data["error"]


def test_predict_invalid_extension(authenticated_client, test_video_file):
    """Тестирует загрузку файла с недопустимым расширением."""
    with open(test_video_file, "rb") as video_file:
        response = authenticated_client.post(
            "/predict",
            data={"file": (video_file, "test_video.txt")},
            content_type="multipart/form-data",
        )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "Недопустимый формат файла" in data["error"]


def test_predict_file_too_large(authenticated_client, test_video_file):
    """Тестирует загрузку слишком большого файла."""
    # Мокируем os.path.getsize, чтобы он возвращал размер больше лимита (100MB)
    with patch("os.path.getsize", return_value=101 * 1024 * 1024):  # 101MB
        with open(test_video_file, "rb") as video_file:
            response = authenticated_client.post(
                "/predict",
                data={"file": (video_file, "test_video.mp4")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Файл слишком большой" in data["error"]


def test_predict_temp_file_not_created(authenticated_client):
    """Тестирует ошибку при создании временного файла."""
    with patch("os.path.exists", return_value=False):  # Имитируем, что файл не создался
        with patch("tempfile.gettempdir", return_value="/tmp"), patch(
            "os.path.join", return_value="/tmp/fake_temp_file"
        ):
            # Нужен фиктивный файл, который будет передан в open
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
            try:
                with open(tmp_file_path, "rb") as video_file:
                    response = authenticated_client.post(
                        "/predict",
                        data={"file": (video_file, "test_video.mp4")},
                        content_type="multipart/form-data",
                    )
                assert response.status_code == 500
                data = json.loads(response.data)
                assert "Ошибка при сохранении временного файла" in data["error"]
            finally:
                os.remove(tmp_file_path)  # Удаляем фиктивный файл


def test_predict_video_processing_error(authenticated_client, test_video_file):
    """Тестирует ошибку при обработке видео."""
    with patch(
        "app.api.routes.video_processing.process_video",
        return_value=(None, None, None, None, None),
    ):  # Имитируем некорректный результат
        with open(test_video_file, "rb") as video_file:
            response = authenticated_client.post(
                "/predict",
                data={"file": (video_file, "test_video.mp4")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Не удалось корректно обработать видео" in data["error"]


def test_predict_db_metadata_error(authenticated_client, test_video_file):
    """Тестирует ошибку БД при сохранении метаданных видео."""
    with patch("app.api.routes.video_processing.process_video") as mock_process, patch(
        "app.api.routes.db_manager.save_video_metadata",
        return_value=(None, "DB Save Error"),
    ):
        mock_process.return_value = (
            "testuser_20230101_video.mp4",  # video_filename
            [[0, 0.8, "person"], [1, 0.7, "car"]],  # frame_objects
            30,  # fps
            False,  # has_weapon
            "testuser_20230101_video.json",  # log_filename
        )
        with open(test_video_file, "rb") as video_file:
            response = authenticated_client.post(
                "/predict",
                data={"file": (video_file, "test_video.mp4")},
                content_type="multipart/form-data",
            )
        # Ожидаем успешный статус, так как ошибка БД логируется, но не прерывает запрос
        assert response.status_code == 200


def test_predict_db_detection_error(authenticated_client, test_video_file):
    """Тестирует ошибку БД при сохранении результатов обнаружения."""
    with patch("app.api.routes.video_processing.process_video") as mock_process, patch(
        "app.api.routes.db_manager.save_video_metadata", return_value=(1, None)
    ), patch(
        "app.api.routes.db_manager.save_detection_results",
        return_value=(False, "DB Detection Error"),
    ):
        mock_process.return_value = (
            "testuser_20230101_video.mp4",  # video_filename
            [[0, 0.8, "person"], [1, 0.7, "car"]],  # frame_objects
            30,  # fps
            False,  # has_weapon
            "testuser_20230101_video.json",  # log_filename
        )
        with open(test_video_file, "rb") as video_file:
            response = authenticated_client.post(
                "/predict",
                data={"file": (video_file, "test_video.mp4")},
                content_type="multipart/form-data",
            )
        # Ожидаем успешный статус, так как ошибка БД логируется, но не прерывает запрос
        assert response.status_code == 200
