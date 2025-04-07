from minio import Minio
from minio.error import S3Error
import os
import json
from datetime import datetime, timedelta

# Параметры для подключения к Minio
# Эти значения будут установлены через переменные окружения в docker-compose
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
MINIO_SECURE = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'

# Имя бакета для хранения видео
VIDEO_BUCKET = 'videos'
LOG_BUCKET = 'logs'

# Клиент Minio
minio_client = None

def init_minio_client():
    """Инициализация клиента Minio"""
    global minio_client
    try:
        minio_client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        # Создаем бакеты, если они не существуют
        if not minio_client.bucket_exists(VIDEO_BUCKET):
            minio_client.make_bucket(VIDEO_BUCKET)
            print(f"Создан бакет {VIDEO_BUCKET}")
        
        if not minio_client.bucket_exists(LOG_BUCKET):
            minio_client.make_bucket(LOG_BUCKET)
            print(f"Создан бакет {LOG_BUCKET}")
            
        return True
    except S3Error as e:
        print(f"Ошибка инициализации Minio: {e}")
        return False

def save_video_to_minio(file_path, object_name):
    """Сохранение видео файла в Minio
    
    Args:
        file_path (str): Путь к видеофайлу на диске
        object_name (str): Имя объекта в Minio (обычно совпадает с именем файла)
        
    Returns:
        bool: True - успешно, False - ошибка
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Определяем content-type для видео
        content_type = 'video/mp4'
        
        # Загружаем файл в Minio
        minio_client.fput_object(
            bucket_name=VIDEO_BUCKET,
            object_name=object_name,
            file_path=file_path,
            content_type=content_type
        )
        
        print(f"Файл {object_name} успешно загружен в Minio")
        return True
    except S3Error as e:
        print(f"Ошибка загрузки файла в Minio: {e}")
        return False

def save_log_to_minio(log_data, object_name):
    """Сохранение JSON лога в Minio
    
    Args:
        log_data (dict): JSON данные для сохранения
        object_name (str): Имя объекта в Minio
        
    Returns:
        bool: True - успешно, False - ошибка
    """
    try:
        if minio_client is None:
            init_minio_client()
        
        # Конвертируем dict в JSON строку
        json_data = json.dumps(log_data).encode('utf-8')
        
        # Загружаем JSON в Minio
        minio_client.put_object(
            bucket_name=LOG_BUCKET,
            object_name=object_name,
            data=json_data,
            length=len(json_data),
            content_type='application/json'
        )
        
        print(f"Лог {object_name} успешно загружен в Minio")
        return True
    except S3Error as e:
        print(f"Ошибка загрузки лога в Minio: {e}")
        return False

def get_video_from_minio(object_name, file_path):
    """Получение видео файла из Minio
    
    Args:
        object_name (str): Имя объекта в Minio
        file_path (str): Путь для сохранения файла
        
    Returns:
        bool: True - успешно, False - ошибка
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Загружаем файл из Minio
        minio_client.fget_object(
            bucket_name=VIDEO_BUCKET,
            object_name=object_name,
            file_path=file_path
        )
        
        return True
    except S3Error as e:
        print(f"Ошибка получения файла из Minio: {e}")
        return False

def get_log_from_minio(object_name):
    """Получение JSON лога из Minio
    
    Args:
        object_name (str): Имя объекта в Minio
        
    Returns:
        dict or None: JSON данные или None в случае ошибки
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Получаем объект из Minio
        response = minio_client.get_object(
            bucket_name=LOG_BUCKET,
            object_name=object_name
        )
        
        # Читаем данные и конвертируем из JSON
        data = response.read().decode('utf-8')
        json_data = json.loads(data)
        
        response.close()
        response.release_conn()
        
        return json_data
    except S3Error as e:
        print(f"Ошибка получения лога из Minio: {e}")
        return None

def delete_from_minio(video_object_name, log_object_name=None):
    """Удаление видео и лога из Minio
    
    Args:
        video_object_name (str): Имя видео объекта в Minio
        log_object_name (str, optional): Имя лог объекта в Minio
        
    Returns:
        bool: True - успешно, False - ошибка
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Удаляем видео
        minio_client.remove_object(
            bucket_name=VIDEO_BUCKET,
            object_name=video_object_name
        )
        
        # Удаляем лог, если он указан
        if log_object_name:
            minio_client.remove_object(
                bucket_name=LOG_BUCKET,
                object_name=log_object_name
            )
        
        return True
    except S3Error as e:
        print(f"Ошибка удаления объектов из Minio: {e}")
        return False

def get_presigned_url(object_name, expires=3600):
    """Создание временной ссылки на видео в Minio
    
    Args:
        object_name (str): Имя объекта в Minio
        expires (int, optional): Время жизни ссылки в секундах
        
    Returns:
        str or None: URL или None в случае ошибки
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Генерируем временную ссылку
        url = minio_client.presigned_get_object(
            bucket_name=VIDEO_BUCKET,
            object_name=object_name,
            expires=timedelta(seconds=expires)
        )
        
        return url
    except S3Error as e:
        print(f"Ошибка создания временной ссылки: {e}")
        return None

def list_user_videos(username):
    """Получение списка видео пользователя из Minio
    
    Args:
        username (str): Имя пользователя
        
    Returns:
        list: Список объектов видео
    """
    try:
        if minio_client is None:
            init_minio_client()
            
        # Получаем список объектов, имя которых начинается с username_
        objects = minio_client.list_objects(
            bucket_name=VIDEO_BUCKET,
            prefix=f"{username}_"
        )
        
        videos = []
        for obj in objects:
            # Для каждого видео проверяем наличие лога
            filename = obj.object_name
            log_exists = False
            log_count = 0
            
            try:
                log_data = get_log_from_minio(f"{filename}.json")
                if log_data:
                    log_exists = True
                    log_count = len(log_data) if log_data else 0
            except:
                pass
            
            parts = filename.split("_")
            if len(parts) >= 3:
                original_name = "_".join(parts[3:])
                videos.append({
                    "filename": filename,
                    "timestamp": parts[1],
                    "original_name": original_name,
                    "has_logs": log_exists,
                    "log_count": log_count,
                    "size": obj.size,
                    "last_modified": obj.last_modified.strftime("%Y-%m-%d %H:%M:%S")
                })
        
        return sorted(videos, key=lambda x: x["timestamp"], reverse=True)
    except S3Error as e:
        print(f"Ошибка получения списка видео: {e}")
        return [] 