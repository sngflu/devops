from datetime import datetime
import json
import os
from app.services import minio_storage
from app.services.minio_storage import MinioStorage

# Используем абсолютные пути относительно директории проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
VIDEOS_DIR = os.path.join(STORAGE_DIR, "videos")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Инициализируем объект MinIO
storage = MinioStorage()

def init_storage():
    """Инициализация хранилища"""
    # Инициализация MinIO
    print("Initializing MinIO storage")
    
    # Также создаем локальные директории для временного хранения
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"Local temporary storage initialized at: {STORAGE_DIR}")
    print(f"Videos directory: {VIDEOS_DIR}")
    print(f"Logs directory: {LOGS_DIR}")


def is_minio_enabled():
    """Проверка, используется ли MinIO как хранилище
    
    Returns:
        bool: True 
    """
    # Всегда возвращаем True для обратной совместимости
    return True


def get_video_path(filename):
    """Получить путь к видео файлу
    
    Args:
        filename (str): Имя файла видео
        
    Returns:
        str: URL к видео (временная ссылка на MinIO)
    """
    # Получаем временную ссылку из MinIO
    return storage.get_presigned_url(filename, expires=3600)


def save_video(video_file, username):
    """Сохранить видео файл
    
    Args:
        video_file: Объект файла
        username: Имя пользователя
        
    Returns:
        str: Имя сохраненного файла
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"{username}_{timestamp}_{video_file.filename}"
    
    # Сначала сохраняем во временный файл
    temp_path = os.path.join("/tmp", video_filename)
    video_file.save(temp_path)
    
    # Загружаем в MinIO
    try:
        metadata = {
            "username": username,
            "original_filename": video_file.filename,
            "uploaded_date": datetime.now().isoformat()
        }
        storage.save_video(temp_path, video_filename, metadata)
    
        # Удаляем временный файл
        os.remove(temp_path)
    except Exception as e:
        print(f"Error saving to MinIO: {str(e)}")
        # Если возникла ошибка, сохраняем локально
        video_path = os.path.join(VIDEOS_DIR, video_filename)
        if temp_path != video_path:
            os.rename(temp_path, video_path)
    
    return video_filename


def save_log(video_filename, frame_objects):
    """Сохранить лог обработки видео
    
    Args:
        video_filename (str): Имя видео файла
        frame_objects (list): Список объектов на кадрах
    """
    # Сохраняем в MinIO
    try:
        storage.save_log(frame_objects, f"{video_filename}.json")
    except Exception as e:
        print(f"Error saving log to MinIO: {str(e)}")
        # Если возникла ошибка, сохраняем локально
        log_filename = f"{video_filename}.json"
        log_path = os.path.join(LOGS_DIR, log_filename)
        with open(log_path, "w") as f:
            json.dump(frame_objects, f)


def get_user_videos(username):
    """Получить список видео пользователя
    
    Args:
        username (str): Имя пользователя
        
    Returns:
        list: Список видео
    """
    # Получаем список видео из MinIO
    try:
        return storage.list_user_videos(username)
    except Exception as e:
        print(f"Error listing videos from MinIO: {str(e)}")
        # Если возникла ошибка, получаем список из локального хранилища
        videos = []
        for filename in os.listdir(VIDEOS_DIR):
            if filename.startswith(username):
                video_path = os.path.join(VIDEOS_DIR, filename)
                log_path = os.path.join(LOGS_DIR, f"{filename}.json")

                if os.path.exists(log_path):
                    with open(log_path, "r") as f:
                        log_data = json.load(f)
                else:
                    log_data = []

                videos.append(
                    {
                        "filename": filename,
                        "timestamp": filename.split("_")[1],
                        "original_name": "_".join(filename.split("_")[3:]),
                        "has_logs": os.path.exists(log_path),
                        "log_count": len(log_data) if log_data else 0,
                        "size": os.path.getsize(video_path),
                        "last_modified": datetime.fromtimestamp(os.path.getmtime(video_path)).strftime("%Y-%m-%d %H:%M:%S")
                    }
                )
        return sorted(videos, key=lambda x: x["timestamp"], reverse=True)


def delete_video(username, filename):
    """Удалить видео и связанные логи
    
    Args:
        username (str): Имя пользователя
        filename (str): Имя файла
        
    Returns:
        tuple: (успех, сообщение)
    """
    if not filename.startswith(f"{username}_"):
        return False, "Unauthorized"

    try:
        # Удаляем из MinIO
        success = storage.delete_objects(filename, f"{filename}.json")
        
        # Также удаляем из локального хранилища, если файлы есть
        video_path = os.path.join(VIDEOS_DIR, filename)
        log_path = os.path.join(LOGS_DIR, f"{filename}.json")

        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(log_path):
            os.remove(log_path)
            
        return success, "Successfully deleted"
    except Exception as e:
        return False, str(e)


def get_video_logs(username, filename):
    """Получить логи видео
    
    Args:
        username (str): Имя пользователя
        filename (str): Имя файла
        
    Returns:
        list or None: Логи видео или None
    """
    if not filename.startswith(f"{username}_"):
        return None

    try:
        # Получаем логи из MinIO
        logs = storage.get_log(f"{filename}.json")
        if logs:
            return logs
    except Exception as e:
        print(f"Error getting logs from MinIO: {str(e)}")
    
    # Если не удалось получить из MinIO, пробуем из локального хранилища
    log_path = os.path.join(LOGS_DIR, f"{filename}.json")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return json.load(f)
    
    return None


def rename_video(username, old_filename, new_name):
    """Переименовать видео файл
    
    Args:
        username (str): Имя пользователя
        old_filename (str): Текущее имя файла
        new_name (str): Новое имя файла
        
    Returns:
        tuple: (успех, сообщение или новое имя)
    """
    if not old_filename.startswith(f"{username}_"):
        return False, "Unauthorized"

    try:
        parts = old_filename.split("_")
        if len(parts) < 4:
            return False, "Invalid filename format"

        new_filename = f"{parts[0]}_{parts[1]}_{parts[2]}_{new_name}"

        # Переименовываем в MinIO
        try:
            storage.rename_object(storage.video_bucket, old_filename, new_filename)
            # Также переименовываем лог, если он существует
            storage.rename_object(storage.log_bucket, f"{old_filename}.json", f"{new_filename}.json")
        except Exception as e:
            print(f"Error renaming in MinIO: {str(e)}")
        
        # Также переименовываем локальные файлы, если они есть
        video_path = os.path.join(VIDEOS_DIR, old_filename)
        new_video_path = os.path.join(VIDEOS_DIR, new_filename)
        log_path = os.path.join(LOGS_DIR, f"{old_filename}.json")
        new_log_path = os.path.join(LOGS_DIR, f"{new_filename}.json")
        
        if os.path.exists(video_path):
            os.rename(video_path, new_video_path)
        if os.path.exists(log_path):
            os.rename(log_path, new_log_path)
                
        return True, new_filename
    except Exception as e:
        return False, str(e)
