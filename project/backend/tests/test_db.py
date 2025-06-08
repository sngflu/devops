import pytest
from unittest.mock import patch, MagicMock, ANY
import psycopg2
from psycopg2.extras import RealDictCursor
import json

from app.services.database.db import DatabaseManager


# Мок для psycopg2.connect
@pytest.fixture
def mock_psycopg2_connect():
    with patch("app.services.database.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        yield mock_connect


# Мок для DatabaseManager с мокированным подключением
@pytest.fixture
def db_manager(mock_psycopg2_connect):
    return DatabaseManager()


def test_get_connection_success(db_manager, mock_psycopg2_connect):
    """Тестирует успешное получение соединения."""
    conn = db_manager.get_connection()
    mock_psycopg2_connect.assert_called_once()
    assert conn is not None


def test_get_connection_failure(db_manager, mock_psycopg2_connect):
    """Тестирует ошибку получения соединения."""
    mock_psycopg2_connect.side_effect = Exception("DB connection error")
    conn = db_manager.get_connection()
    mock_psycopg2_connect.assert_called_once()
    assert conn is None


def test_init_database_success(db_manager, mock_psycopg2_connect):
    """Тестирует успешную инициализацию БД."""
    mock_conn = mock_psycopg2_connect.return_value
    result = db_manager.init_database()
    mock_psycopg2_connect.assert_called_once()
    mock_conn.close.assert_called_once()
    assert result is True


def test_init_database_failure(db_manager, mock_psycopg2_connect):
    """Тестирует ошибку инициализации БД."""
    mock_psycopg2_connect.return_value = None
    result = db_manager.init_database()
    mock_psycopg2_connect.assert_called_once()
    assert result is False


def test_execute_query_select_one(db_manager, mock_psycopg2_connect):
    """Тестирует выполнение SELECT запроса с fetch='one'."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": 1, "name": "test"}

    query = "SELECT * FROM users WHERE id = %s"
    params = (1,)
    result, error = db_manager.execute_query(query, params=params, fetch="one")

    mock_conn.cursor.assert_called_once_with(cursor_factory=None)
    mock_cursor.execute.assert_called_once_with(query, params)
    mock_cursor.fetchone.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()
    assert result == {"id": 1, "name": "test"}
    assert error is None


def test_execute_query_select_all(db_manager, mock_psycopg2_connect):
    """Тестирует выполнение SELECT запроса с fetch='all'."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        {"id": 1, "name": "test1"},
        {"id": 2, "name": "test2"},
    ]

    query = "SELECT * FROM users"
    result, error = db_manager.execute_query(query, fetch="all")

    mock_conn.cursor.assert_called_once_with(cursor_factory=None)
    mock_cursor.execute.assert_called_once_with(query, ())
    mock_cursor.fetchall.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()
    assert result == [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
    assert error is None


def test_execute_query_insert(db_manager, mock_psycopg2_connect):
    """Тестирует выполнение INSERT запроса."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    query = "INSERT INTO users (name) VALUES (%s)"
    params = ("test",)
    result, error = db_manager.execute_query(query, params=params, fetch="none")

    mock_conn.cursor.assert_called_once_with(cursor_factory=None)
    mock_cursor.execute.assert_called_once_with(query, params)
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()
    assert result is None
    assert error is None


def test_execute_query_unique_violation(db_manager, mock_psycopg2_connect):
    """Тестирует обработку psycopg2.errors.UniqueViolation."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = psycopg2.errors.UniqueViolation()

    query = "INSERT INTO users (name) VALUES (%s)"
    params = ("test",)
    result, error = db_manager.execute_query(query, params=params)

    mock_conn.cursor.assert_called_once_with(cursor_factory=None)
    mock_cursor.execute.assert_called_once_with(query, params)
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()
    assert result is None
    assert "Нарушение ограничения уникальности" in error


def test_execute_query_other_exception(db_manager, mock_psycopg2_connect):
    """Тестирует обработку других исключений при выполнении запроса."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("Some other error")

    query = "SELECT * FROM users"
    result, error = db_manager.execute_query(query)

    mock_conn.cursor.assert_called_once_with(cursor_factory=None)
    mock_cursor.execute.assert_called_once_with(query, ())
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()
    assert result is None
    assert "Ошибка выполнения запроса" in error


def test_execute_query_connection_error(db_manager, mock_psycopg2_connect):
    """Тестирует обработку ошибки подключения в execute_query."""
    mock_psycopg2_connect.return_value = None

    query = "SELECT * FROM users"
    result, error = db_manager.execute_query(query)

    mock_psycopg2_connect.assert_called_once()
    assert result is None
    assert "Ошибка подключения к БД" in error


# Тесты для transaction контекстного менеджера
def test_transaction_success(db_manager, mock_psycopg2_connect):
    """Тестирует успешное выполнение транзакции."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with db_manager.transaction() as cursor:
        cursor.execute("INSERT INTO test (col) VALUES (%s)", ("value",))

    mock_psycopg2_connect.assert_called_once()
    mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
    mock_cursor.execute.assert_called_once_with(
        "INSERT INTO test (col) VALUES (%s)", ("value",)
    )
    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    mock_conn.close.assert_called_once()


def test_transaction_rollback_on_exception(db_manager, mock_psycopg2_connect):
    """Тестирует откат транзакции при исключении."""
    mock_conn = mock_psycopg2_connect.return_value
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("Transaction error")

    with pytest.raises(Exception, match="Transaction error"):
        with db_manager.transaction() as cursor:
            cursor.execute("INSERT INTO test (col) VALUES (%s)", ("value",))

    mock_psycopg2_connect.assert_called_once()
    mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
    mock_cursor.execute.assert_called_once_with(
        "INSERT INTO test (col) VALUES (%s)", ("value",)
    )
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_transaction_connection_error(db_manager, mock_psycopg2_connect):
    """Тестирует ошибку подключения в контекстном менеджере transaction."""
    mock_psycopg2_connect.return_value = None

    with pytest.raises(
        Exception, match="Не удалось установить соединение с базой данных"
    ):
        with db_manager.transaction() as cursor:
            pass  # This part should not be reached

    mock_psycopg2_connect.assert_called_once()
    # conn.close should not be called if get_connection returns None


# Тесты для методов работы с пользователями
def test_get_user_by_username_success(db_manager):
    """Тестирует успешное получение пользователя по имени."""
    mock_user_data = {"user_id": 1, "username": "testuser"}
    with patch.object(
        db_manager, "execute_query", return_value=(mock_user_data, None)
    ) as mock_exec_query:
        user = db_manager.get_user_by_username("testuser")

        mock_exec_query.assert_called_once_with(
            """SELECT * FROM users WHERE username = %s""",
            ("testuser",),
            fetch="one",
            cursor_factory=RealDictCursor,
        )
        assert user == mock_user_data


def test_get_user_by_username_not_found(db_manager):
    """Тестирует получение несуществующего пользователя."""
    with patch.object(
        db_manager, "execute_query", return_value=(None, None)
    ) as mock_exec_query:
        user = db_manager.get_user_by_username("nonexistent")

        mock_exec_query.assert_called_once_with(
            """SELECT * FROM users WHERE username = %s""",
            ("nonexistent",),
            fetch="one",
            cursor_factory=RealDictCursor,
        )
        assert user is None


def test_create_user_success(db_manager):
    """Тестирует успешное создание пользователя."""
    mock_return_data = {"user_id": 1}
    with patch.object(
        db_manager, "execute_query", return_value=(mock_return_data, None)
    ) as mock_exec_query:
        user_id, error = db_manager.create_user("newuser", "hashed_password", "user")

        mock_exec_query.assert_called_once()
        assert user_id == 1
        assert error is None


def test_create_user_duplicate_username(db_manager):
    """Тестирует создание пользователя с дублирующимся именем."""
    error_message = "Пользователь с таким именем уже существует"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id, error = db_manager.create_user("existinguser", "hashed_password")

        mock_exec_query.assert_called_once()
        assert user_id is None
        assert error == error_message


def test_create_user_other_error(db_manager):
    """Тестирует создание пользователя при другой ошибке БД."""
    error_message = "Some database error"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id, error = db_manager.create_user("anotheruser", "hashed_password")

        mock_exec_query.assert_called_once()
        assert user_id is None
        assert error == error_message


# Тесты для методов работы с видео
def test_save_video_metadata_success(db_manager):
    """Тестирует успешное сохранение метаданных видео."""
    mock_return_data = {"video_id": 10}
    with patch.object(
        db_manager, "execute_query", return_value=(mock_return_data, None)
    ) as mock_exec_query:
        user_id = 1
        s3_key = "videos/test_video.mp4"
        bucket_name = "my-bucket"
        metadata = {"duration": 60}
        video_id, error = db_manager.save_video_metadata(
            user_id, s3_key, bucket_name, metadata
        )

        mock_exec_query.assert_called_once()
        assert video_id == 10
        assert error is None


def test_save_video_metadata_error(db_manager):
    """Тестирует ошибку при сохранении метаданных видео."""
    error_message = "DB error saving metadata"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id = 1
        s3_key = "videos/test_video.mp4"
        bucket_name = "my-bucket"
        metadata = {"duration": 60}
        video_id, error = db_manager.save_video_metadata(
            user_id, s3_key, bucket_name, metadata
        )

        mock_exec_query.assert_called_once()
        assert video_id is None
        assert error == error_message


def test_save_video_metadata_success_no_metadata(db_manager):
    """Тестирует успешное сохранение метаданных видео без предоставления метаданных."""
    mock_return_data = {"video_id": 11}
    with patch.object(
        db_manager, "execute_query", return_value=(mock_return_data, None)
    ) as mock_exec_query:
        user_id = 1
        s3_key = "videos/another_video.mp4"
        bucket_name = "my-bucket"
        # metadata = None (по умолчанию)
        video_id, error = db_manager.save_video_metadata(user_id, s3_key, bucket_name)

        mock_exec_query.assert_called_once_with(
            """
            INSERT INTO videos (user_id, s3_key, bucket_name, status, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING video_id
            """,
            (
                user_id,
                s3_key,
                bucket_name,
                "pending",
                json.dumps({}),
            ),  # Ожидаем пустой JSON
            fetch="one",
            cursor_factory=RealDictCursor,
        )
        assert video_id == 11
        assert error is None


def test_update_video_status_success(db_manager):
    """Тестирует успешное обновление статуса видео."""
    with patch.object(
        db_manager, "execute_query", return_value=(None, None)
    ) as mock_exec_query:
        video_id = 10
        status = "processed"
        success, error = db_manager.update_video_status(video_id, status)

        mock_exec_query.assert_called_once_with(
            """
            UPDATE videos 
            SET status = %s
            WHERE video_id = %s
            """,
            (status, video_id),
            fetch=None,
        )
        assert success is True
        assert error is None


def test_update_video_status_error(db_manager):
    """Тестирует ошибку при обновлении статуса видео."""
    error_message = "DB error updating status"
    with patch.object(
        db_manager, "execute_query", return_value=(False, error_message)
    ) as mock_exec_query:
        video_id = 10
        status = "failed"
        success, error = db_manager.update_video_status(video_id, status)

        mock_exec_query.assert_called_once_with(
            """
            UPDATE videos 
            SET status = %s
            WHERE video_id = %s
            """,
            (status, video_id),
            fetch=None,
        )
        assert success is False
        assert error == error_message


def test_rename_video_success(db_manager):
    """Тестирует успешное переименование видео."""
    mock_video_data = {"s3_key": "old/key.mp4"}
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_cursor = MagicMock()
        mock_transaction.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_video_data

        video_id = 10
        user_id = 1
        new_s3_key = "new/key.mp4"

        success, error = db_manager.rename_video(video_id, user_id, new_s3_key)

        mock_transaction.assert_called_once()
        mock_cursor.execute.assert_any_call(
            """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        mock_cursor.execute.assert_any_call(
            """
                    INSERT INTO logs (user_id, action, video_id, details)
                    VALUES (%s, %s, %s, %s)
                    """,
            (user_id, "rename", video_id, ANY),
        )
        mock_cursor.execute.assert_any_call(
            """
                    UPDATE videos 
                    SET s3_key = %s
                    WHERE video_id = %s
                    """,
            (new_s3_key, video_id),
        )
        assert success is True
        assert error is None


def test_rename_video_not_found(db_manager):
    """Тестирует переименование несуществующего видео."""
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_cursor = MagicMock()
        mock_transaction.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Video not found

        video_id = 10
        user_id = 1
        new_s3_key = "new/key.mp4"

        success, error = db_manager.rename_video(video_id, user_id, new_s3_key)

        mock_transaction.assert_called_once()
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        mock_cursor.execute.assert_any_call(
            """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )  # Only the SELECT should be called
        mock_cursor.execute.call_count = 1  # Ensure only SELECT was called

        assert success is False
        assert error == "Видео не найдено или нет доступа"


def test_rename_video_exception(db_manager):
    """Тестирует обработку исключения при переименовании видео."""
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_transaction.side_effect = Exception("Rename transaction error")

        video_id = 10
        user_id = 1
        new_s3_key = "new/key.mp4"

        success, error = db_manager.rename_video(video_id, user_id, new_s3_key)

        mock_transaction.assert_called_once()
        assert success is False
        assert "Ошибка при переименовании видео: Rename transaction error" in error


def test_get_user_videos_success(db_manager):
    """Тестирует успешное получение видео пользователя."""
    mock_videos_data = [
        {"video_id": 10, "s3_key": "video1.mp4"},
        {"video_id": 11, "s3_key": "video2.mp4"},
    ]
    with patch.object(
        db_manager, "execute_query", return_value=(mock_videos_data, None)
    ) as mock_exec_query:
        user_id = 1
        videos = db_manager.get_user_videos(user_id)

        mock_exec_query.assert_called_once_with(
            """
            SELECT v.*, 
                   CASE WHEN dr.weapon_detected THEN true ELSE false END as weapon_detected,
                   dr.result_id
            FROM videos v
            LEFT JOIN detection_results dr ON v.video_id = dr.video_id
            WHERE v.user_id = %s
            ORDER BY v.upload_time DESC
            """,
            (user_id,),
            fetch="all",
            cursor_factory=RealDictCursor,
        )
        assert videos == mock_videos_data


def test_get_user_videos_error(db_manager):
    """Тестирует ошибку при получении видео пользователя."""
    error_message = "DB error getting user videos"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id = 1
        videos = db_manager.get_user_videos(user_id)

        mock_exec_query.assert_called_once_with(
            """
            SELECT v.*, 
                   CASE WHEN dr.weapon_detected THEN true ELSE false END as weapon_detected,
                   dr.result_id
            FROM videos v
            LEFT JOIN detection_results dr ON v.video_id = dr.video_id
            WHERE v.user_id = %s
            ORDER BY v.upload_time DESC
            """,
            (user_id,),
            fetch="all",
            cursor_factory=RealDictCursor,
        )
        assert videos == []


def test_get_video_by_s3_key_success(db_manager):
    """Тестирует успешное получение видео по ключу S3."""
    mock_video_data = {"video_id": 10, "s3_key": "video1.mp4"}
    with patch.object(
        db_manager, "execute_query", return_value=(mock_video_data, None)
    ) as mock_exec_query:
        s3_key = "video1.mp4"
        video = db_manager.get_video_by_s3_key(s3_key)

        mock_exec_query.assert_called_once_with(
            """
            SELECT * FROM videos 
            WHERE s3_key = %s
            """,
            (s3_key,),
            fetch="one",
            cursor_factory=RealDictCursor,
        )
        assert video == mock_video_data


def test_get_video_by_s3_key_not_found(db_manager):
    """Тестирует получение несуществующего видео по ключу S3."""
    with patch.object(
        db_manager, "execute_query", return_value=(None, None)
    ) as mock_exec_query:
        s3_key = "nonexistent.mp4"
        video = db_manager.get_video_by_s3_key(s3_key)

        mock_exec_query.assert_called_once_with(
            """
            SELECT * FROM videos 
            WHERE s3_key = %s
            """,
            (s3_key,),
            fetch="one",
            cursor_factory=RealDictCursor,
        )
        assert video is None


def test_delete_video_success(db_manager):
    """Тестирует успешное удаление видео."""
    mock_video_data = {"s3_key": "video_to_delete.mp4", "bucket_name": "my-bucket"}
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_cursor = MagicMock()
        mock_transaction.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [
            mock_video_data,
            None,
        ]  # First fetchone for video data, second for delete result

        video_id = 20
        user_id = 1

        success, result = db_manager.delete_video(video_id, user_id)

        mock_transaction.assert_called_once()
        mock_cursor.execute.assert_any_call(
            """
                    SELECT s3_key, bucket_name FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        mock_cursor.execute.assert_any_call(
            """
                    INSERT INTO logs (user_id, action, video_id, details)
                    VALUES (%s, %s, %s, %s)
                    """,
            (user_id, "delete", video_id, ANY),
        )
        mock_cursor.execute.assert_any_call(
            """
                    DELETE FROM videos 
                    WHERE video_id = %s
                    """,
            (video_id,),
        )
        assert success is True
        assert result == mock_video_data


def test_delete_video_not_found(db_manager):
    """Тестирует удаление несуществующего видео."""
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_cursor = MagicMock()
        mock_transaction.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Video not found

        video_id = 20
        user_id = 1

        success, error = db_manager.delete_video(video_id, user_id)

        mock_transaction.assert_called_once()
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT s3_key, bucket_name FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """,
            (video_id, user_id),
        )
        # Check that delete and log insert were not called
        mock_cursor.execute.call_count = 1
        assert success is False
        assert error == "Видео не найдено или нет доступа"


def test_delete_video_exception(db_manager):
    """Тестирует обработку исключения при удалении видео."""
    with patch.object(db_manager, "transaction") as mock_transaction:
        mock_transaction.side_effect = Exception("Delete transaction error")

        video_id = 20
        user_id = 1

        success, error = db_manager.delete_video(video_id, user_id)

        mock_transaction.assert_called_once()
        assert success is False
        assert "Ошибка при удалении видео: Delete transaction error" in error


def test_save_detection_results_success(db_manager):
    """Тестирует успешное сохранение результатов детекции."""
    mock_video_data = {"user_id": 1, "s3_key": "video.mp4", "bucket_name": "videos"}
    mock_result_data = {"result_id": 100}

    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [mock_video_data, mock_result_data]

        video_id = 10
        log_filename = "log.json"
        frame_objects = [(1, True, False)]
        weapon_detected = True

        success, error = db_manager.save_detection_results(
            video_id, log_filename, frame_objects, weapon_detected
        )

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_any_call(
            """
                SELECT user_id, s3_key, bucket_name FROM videos
                WHERE video_id = %s
                """,
            (video_id,),
        )
        mock_cursor.execute.assert_any_call(
            """
                INSERT INTO detection_results 
                (video_id, user_id, s3_key, bucket_name, status, weapon_detected)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING result_id
                """,
            (video_id, 1, log_filename, "logs", "completed", weapon_detected),
        )
        mock_cursor.execute.assert_any_call(
            """
                UPDATE videos 
                SET status = 'completed'
                WHERE video_id = %s
                """,
            (video_id,),
        )
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()
        mock_conn.close.assert_called_once()
        assert success is True
        assert error is None


def test_save_detection_results_connection_error(db_manager):
    """Тестирует ошибку подключения при сохранении результатов детекции."""
    with patch.object(db_manager, "get_connection", return_value=None) as mock_get_conn:
        video_id = 10
        log_filename = "log.json"
        frame_objects = []
        weapon_detected = False

        success, error = db_manager.save_detection_results(
            video_id, log_filename, frame_objects, weapon_detected
        )

        mock_get_conn.assert_called_once()
        assert success is False
        assert error == "Ошибка подключения к БД"


def test_save_detection_results_video_not_found(db_manager):
    """Тестирует сохранение результатов детекции для несуществующего видео."""
    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Video not found

        video_id = 10
        log_filename = "log.json"
        frame_objects = []
        weapon_detected = False

        success, error = db_manager.save_detection_results(
            video_id, log_filename, frame_objects, weapon_detected
        )

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_called_once_with(
            """
                SELECT user_id, s3_key, bucket_name FROM videos
                WHERE video_id = %s
                """,
            (video_id,),
        )
        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_not_called()
        mock_conn.close.assert_called_once()
        assert success is False
        assert f"Видео с ID {video_id} не найдено" in error


def test_save_detection_results_exception(db_manager):
    """Тестирует обработку исключения при сохранении результатов детекции."""
    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Detection save error")

        video_id = 10
        log_filename = "log.json"
        frame_objects = []
        weapon_detected = False

        success, error = db_manager.save_detection_results(
            video_id, log_filename, frame_objects, weapon_detected
        )

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
        assert success is False
        assert (
            "Ошибка при сохранении результатов обнаружения: Detection save error"
            in error
        )


def test_get_video_detections_success(db_manager):
    """Тестирует успешное получение результатов детекции видео."""
    mock_detection_data = {"result_id": 100, "weapon_detected": True}
    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_detection_data

        video_id = 10
        results = db_manager.get_video_detections(video_id)

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_called_once_with(
            """
                SELECT dr.*, v.s3_key as video_s3_key, v.bucket_name as video_bucket_name
                FROM detection_results dr
                JOIN videos v ON dr.video_id = v.video_id
                WHERE dr.video_id = %s
                """,
            (video_id,),
        )
        mock_conn.close.assert_called_once()
        assert results == mock_detection_data


def test_get_video_detections_not_found(db_manager):
    """Тестирует получение результатов детекции для видео без результатов."""
    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        video_id = 10
        results = db_manager.get_video_detections(video_id)

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_called_once_with(
            """
                SELECT dr.*, v.s3_key as video_s3_key, v.bucket_name as video_bucket_name
                FROM detection_results dr
                JOIN videos v ON dr.video_id = v.video_id
                WHERE dr.video_id = %s
                """,
            (video_id,),
        )
        mock_conn.close.assert_called_once()
        assert results is None


def test_get_video_detections_connection_error(db_manager):
    """Тестирует ошибку подключения при получении результатов детекции."""
    with patch.object(db_manager, "get_connection", return_value=None) as mock_get_conn:
        video_id = 10
        results = db_manager.get_video_detections(video_id)

        mock_get_conn.assert_called_once()
        assert results is None


def test_get_video_detections_exception(db_manager):
    """Тестирует обработку исключения при получении результатов детекции."""
    with patch.object(db_manager, "get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Detection retrieve error")

        video_id = 10
        results = db_manager.get_video_detections(video_id)

        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        mock_cursor.execute.assert_called_once_with(
            """
                SELECT dr.*, v.s3_key as video_s3_key, v.bucket_name as video_bucket_name
                FROM detection_results dr
                JOIN videos v ON dr.video_id = v.video_id
                WHERE dr.video_id = %s
                """,
            (video_id,),
        )
        mock_conn.close.assert_called_once()
        assert results is None


def test_add_log_with_details_success(db_manager):
    """Тестирует успешное добавление записи в журнал с деталями."""
    with patch.object(
        db_manager, "execute_query", return_value=(None, None)
    ) as mock_exec_query:
        user_id = 1
        action = "login"
        video_id = 10
        details = {"ip": "127.0.0.1"}

        success = db_manager.add_log(user_id, action, video_id, details)

        mock_exec_query.assert_called_once_with(
            """
            INSERT INTO logs (user_id, action, video_id, details)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, action, video_id, json.dumps(details)),
            fetch=None,
        )
        assert success is True  # add_log returns True on success now


def test_add_log_without_details_success(db_manager):
    """Тестирует успешное добавление записи в журнал без деталей."""
    with patch.object(
        db_manager, "execute_query", return_value=(None, None)
    ) as mock_exec_query:
        user_id = 1
        action = "logout"

        success = db_manager.add_log(user_id, action)

        mock_exec_query.assert_called_once_with(
            """
            INSERT INTO logs (user_id, action, video_id)
            VALUES (%s, %s, %s)
            """,
            (user_id, action, None),  # video_id should be None
            fetch=None,
        )
        assert success is True  # add_log returns True on success now


def test_add_log_error(db_manager):
    """Тестирует ошибку при добавлении записи в журнал."""
    error_message = "Log insert failed"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id = 1
        action = "error"

        success = db_manager.add_log(user_id, action)

        mock_exec_query.assert_called_once()
        assert success is False  # add_log returns False on error now


def test_get_user_logs_success(db_manager):
    """Тестирует успешное получение журнала действий пользователя."""
    mock_logs_data = [{"log_id": 1, "action": "login"}]
    with patch.object(
        db_manager, "execute_query", return_value=(mock_logs_data, None)
    ) as mock_exec_query:
        user_id = 1
        limit = 50
        logs = db_manager.get_user_logs(user_id, limit)

        mock_exec_query.assert_called_once_with(
            """
            SELECT l.*, v.s3_key
            FROM logs l
            LEFT JOIN videos v ON l.video_id = v.video_id
            WHERE l.user_id = %s
            ORDER BY l.timestamp DESC
            LIMIT %s
            """,
            (user_id, limit),
            fetch="all",
            cursor_factory=RealDictCursor,
        )
        assert logs == mock_logs_data


def test_get_user_logs_error(db_manager):
    """Тестирует ошибку при получении журнала действий пользователя."""
    error_message = "Error fetching logs"
    with patch.object(
        db_manager, "execute_query", return_value=(None, error_message)
    ) as mock_exec_query:
        user_id = 1
        limit = 50
        logs = db_manager.get_user_logs(user_id, limit)

        mock_exec_query.assert_called_once_with(
            """
            SELECT l.*, v.s3_key
            FROM logs l
            LEFT JOIN videos v ON l.video_id = v.video_id
            WHERE l.user_id = %s
            ORDER BY l.timestamp DESC
            LIMIT %s
            """,
            (user_id, limit),
            fetch="all",
            cursor_factory=RealDictCursor,
        )
        assert logs == []  # Expect empty list on error
