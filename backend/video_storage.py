from datetime import datetime
import json
import os
import minio_storage

STORAGE_DIR = "storage"
VIDEOS_DIR = os.path.join(STORAGE_DIR, "videos")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Флаг для включения/отключения использования Minio
USE_MINIO = os.environ.get('USE_MINIO', 'true').lower() == 'true'


def init_storage():
    """Инициализирует хранилище данных"""
    if USE_MINIO:
        # Инициализируем клиент Minio
        if not minio_storage.init_minio_client():
            print("Ошибка инициализации Minio, используем локальное хранилище")
            global USE_MINIO
            USE_MINIO = False
            
    # Всегда создаем локальные директории (они могут использоваться 
    # как временное хранилище даже при работе с Minio)
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def save_video(video_file, username):
    """Сохраняет видео файл и возвращает его имя
    
    Args:
        video_file: Файл из запроса Flask
        username: Имя пользователя
        
    Returns:
        str: Имя сохраненного файла
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"{username}_{timestamp}_{video_file.filename}"
    
    # Сначала сохраняем в локальную файловую систему
    video_path = os.path.join(VIDEOS_DIR, video_filename)
    video_file.save(video_path)
    
    if USE_MINIO:
        # Если используем Minio, то загружаем файл в S3
        minio_storage.save_video_to_minio(video_path, video_filename)
        
        # После загрузки в Minio, можно удалить локальный файл 
        # чтобы не занимать место на диске
        # os.remove(video_path)  # Пока оставим, чтобы была возможность использовать обе системы
    
    return video_filename


def save_log(video_filename, frame_objects):
    """Сохраняет лог для видео
    
    Args:
        video_filename: Имя файла видео
        frame_objects: Данные лога
    """
    log_filename = f"{video_filename}.json"
    
    # Сохраняем в локальной файловой системе
    log_path = os.path.join(LOGS_DIR, log_filename)
    with open(log_path, "w") as f:
        json.dump(frame_objects, f)
    
    if USE_MINIO:
        # Сохраняем лог в Minio
        minio_storage.save_log_to_minio(frame_objects, log_filename)
        
        # После загрузки в Minio, можно удалить локальный файл
        # os.remove(log_path)  # Пока оставим, чтобы была возможность использовать обе системы


def get_user_videos(username):
    """Получает список видео пользователя
    
    Args:
        username: Имя пользователя
        
    Returns:
        list: Список видео с метаданными
    """
    if USE_MINIO:
        # Получаем список видео из Minio
        return minio_storage.list_user_videos(username)
    
    # Получаем список видео из локальной файловой системы
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
                }
            )
    return sorted(videos, key=lambda x: x["timestamp"], reverse=True)


def delete_video(username, filename):
    """Удаляет видео и связанные с ним логи
    
    Args:
        username: Имя пользователя
        filename: Имя файла
        
    Returns:
        (bool, str): (Успех операции, Сообщение)
    """
    if not filename.startswith(f"{username}_"):
        return False, "Unauthorized"

    if USE_MINIO:
        # Удаляем видео и лог из Minio
        log_filename = f"{filename}.json"
        success = minio_storage.delete_from_minio(filename, log_filename)
        if success:
            return True, "Successfully deleted"
        else:
            return False, "Error while deleting from Minio"

    # Удаляем из локальной файловой системы
    video_path = os.path.join(VIDEOS_DIR, filename)
    log_path = os.path.join(LOGS_DIR, f"{filename}.json")

    try:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(log_path):
            os.remove(log_path)
        return True, "Successfully deleted"
    except Exception as e:
        return False, str(e)


def get_video_logs(username, filename):
    """Получает логи для видео
    
    Args:
        username: Имя пользователя
        filename: Имя файла
        
    Returns:
        dict or None: Данные лога или None
    """
    if not filename.startswith(f"{username}_"):
        return None

    if USE_MINIO:
        # Получаем лог из Minio
        log_filename = f"{filename}.json"
        return minio_storage.get_log_from_minio(log_filename)

    # Получаем лог из локальной файловой системы
    log_path = os.path.join(LOGS_DIR, f"{filename}.json")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return json.load(f)
    return None


def rename_video(username, old_filename, new_name):
    """Переименовывает видео
    
    Args:
        username: Имя пользователя
        old_filename: Старое имя файла
        new_name: Новое имя файла
        
    Returns:
        (bool, str): (Успех операции, Сообщение или новое имя файла)
    """
    if not old_filename.startswith(f"{username}_"):
        return False, "Unauthorized"

    try:
        parts = old_filename.split("_")
        if len(parts) < 4:
            return False, "Invalid filename format"

        new_filename = f"{parts[0]}_{parts[1]}_{parts[2]}_{new_name}"

        if USE_MINIO:
            # TODO: в Minio нет прямой функции переименования, 
            # нужно будет копировать объекты и удалять старые
            # Это можно реализовать в будущем
            return False, "Renaming not implemented for Minio storage"

        old_video_path = os.path.join(VIDEOS_DIR, old_filename)
        new_video_path = os.path.join(VIDEOS_DIR, new_filename)
        old_log_path = os.path.join(LOGS_DIR, f"{old_filename}.json")
        new_log_path = os.path.join(LOGS_DIR, f"{new_filename}.json")

        if os.path.exists(old_video_path):
            os.rename(old_video_path, new_video_path)
        if os.path.exists(old_log_path):
            os.rename(old_log_path, new_log_path)

        return True, new_filename
    except Exception as e:
        return False, str(e)


def get_video_path(filename):
    """Получает полный путь к видео файлу
    
    Args:
        filename: Имя файла
        
    Returns:
        str: Полный путь к файлу или временная ссылка на Minio
    """
    if USE_MINIO:
        # Возвращаем временную ссылку на видео в Minio
        return minio_storage.get_presigned_url(filename)
    
    # Возвращаем локальный путь к файлу
    return os.path.join(VIDEOS_DIR, filename)


def is_minio_enabled():
    """Проверяет, используется ли Minio
    
    Returns:
        bool: True если Minio используется
    """
    return USE_MINIO
