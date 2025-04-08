from minio import Minio
from minio.error import S3Error
from minio.commonconfig import CopySource
import os
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
import io

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def retry_s3_operation(max_retries=3, backoff_factor=0.3):
    """Декоратор для повторения операций S3 при ошибках"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            retry_count = 0
            logger.debug(f"Вызов функции {func.__name__} с аргументами: {args}, {kwargs}")
            while retry_count < max_retries:
                try:
                    result = func(self, *args, **kwargs)
                    logger.debug(f"Функция {func.__name__} выполнена успешно")
                    return result
                except S3Error as e:
                    # Некоторые ошибки не стоит повторять
                    if e.code in ["NoSuchKey", "AccessDenied"]:
                        logger.error(f"Критическая ошибка S3 в {func.__name__}: {e}. Повтор невозможен.")
                        raise
                    
                    retry_count += 1
                    wait_time = backoff_factor * (2 ** retry_count)
                    logger.warning(f"Ошибка S3 в {func.__name__}: {e}. Повтор {retry_count}/{max_retries} через {wait_time} сек.")
                    
                    if retry_count < max_retries:
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Исчерпаны все попытки выполнения {func.__name__}. Последняя ошибка: {e}")
                        raise
        return wrapper
    return decorator

class MinioStorage:
    """Улучшенный класс для работы с MinIO хранилищем"""
    
    def __init__(
        self,
        endpoint=os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
        access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
        secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
        secure=os.environ.get('MINIO_SECURE', 'false').lower() == 'true',
        video_bucket='videos',
        log_bucket='logs',
        region=None
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.video_bucket = video_bucket
        self.log_bucket = log_bucket
        self.region = region
        self.client = None
        logger.info(f"Инициализация MinioStorage с параметрами: endpoint={endpoint}, secure={secure}, region={region}")
        self.connect()
        
    def connect(self):
        """Установка соединения с MinIO"""
        logger.info(f"Попытка установки соединения с MinIO по адресу {self.endpoint}")
        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                region=self.region
            )
            
            self._ensure_buckets_exist()
            
            logger.info("Соединение с MinIO установлено успешно")
            return True
        except S3Error as e:
            logger.error(f"Ошибка инициализации Minio: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении к MinIO: {e}")
            return False
    
    def _ensure_buckets_exist(self):
        """Проверка и создание необходимых бакетов"""
        logger.debug("Проверка существования необходимых бакетов")
        try:
            if not self.client.bucket_exists(self.video_bucket):
                logger.info(f"Бакет {self.video_bucket} не существует, создаем")
                self.client.make_bucket(self.video_bucket)
                logger.info(f"Создан бакет {self.video_bucket}")
            else:
                logger.debug(f"Бакет {self.video_bucket} уже существует")
            
            if not self.client.bucket_exists(self.log_bucket):
                logger.info(f"Бакет {self.log_bucket} не существует, создаем")
                self.client.make_bucket(self.log_bucket)
                logger.info(f"Создан бакет {self.log_bucket}")
            else:
                logger.debug(f"Бакет {self.log_bucket} уже существует")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке/создании бакетов: {e}")
            raise
    
    def check_connection(self):
        """Проверка работоспособности соединения"""
        logger.debug("Проверка работоспособности соединения с MinIO")
        try:
            buckets = self.client.list_buckets()
            logger.debug(f"Соединение работает, доступные бакеты: {', '.join([b.name for b in buckets])}")
            return True
        except Exception as e:
            logger.warning(f"Проверка соединения не удалась: {e}")
            return False
    
    def ensure_connection(self):
        """Проверяет соединение и устанавливает его при необходимости"""
        logger.debug("Проверка необходимости переподключения к MinIO")
        if self.client is None:
            logger.info("Клиент MinIO не инициализирован, выполняется подключение")
            return self.connect()
        if not self.check_connection():
            logger.info("Соединение с MinIO потеряно, выполняется переподключение")
            return self.connect()
        return True
            
    @retry_s3_operation()
    def save_video(self, file_path, object_name, metadata=None):
        """Сохранение видео файла в Minio с поддержкой метаданных"""
        logger.info(f"Загрузка видео файла {file_path} в MinIO с именем {object_name}")
        try:
            self.ensure_connection()
            
            content_type = 'video/mp4'
            
            file_size = os.path.getsize(file_path)
            logger.debug(f"Размер загружаемого файла: {file_size} байт")
            
            self.client.fput_object(
                bucket_name=self.video_bucket,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type,
                metadata=metadata
            )
            
            logger.info(f"Файл {object_name} успешно загружен в Minio")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении видео: {e}")
            return False
    
    @retry_s3_operation()
    def save_log(self, log_data, object_name, metadata=None):
        """Сохранение JSON лога в Minio"""
        logger.info(f"Сохранение лога в MinIO с именем {object_name}")
        self.ensure_connection()
        
        json_data = json.dumps(log_data).encode('utf-8')
        logger.debug(f"Размер JSON данных: {len(json_data)} байт")
        
        bytes_io = io.BytesIO(json_data)
        
        self.client.put_object(
            bucket_name=self.log_bucket,
            object_name=object_name,
            data=bytes_io,
            length=len(json_data),
            content_type='application/json',
            metadata=metadata
        )
        
        logger.info(f"Лог {object_name} успешно загружен в Minio")
        return True
    
    @retry_s3_operation()
    def rename_object(self, source_bucket, source_object, target_object):
        """Переименование объекта через операцию копирования"""
        logger.info(f"Переименование объекта {source_object} в {target_object} в бакете {source_bucket}")
        try:
            self.ensure_connection()
            
            self.client.copy_object(
                bucket_name=source_bucket,
                object_name=target_object,
                source_bucket_name=source_bucket,
                source_object_name=source_object
            )
            
            self.client.remove_object(
                bucket_name=source_bucket,
                object_name=source_object
            )
            
            logger.info(f"Объект {source_object} переименован в {target_object}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при переименовании объекта: {e}")
            return False
    
    @retry_s3_operation()
    def get_video(self, object_name, file_path):
        """Получение видео файла из Minio
        
        Args:
            object_name (str): Имя объекта в Minio
            file_path (str): Путь для сохранения файла
            
        Returns:
            bool: True - успешно, False - ошибка
        """
        logger.info(f"Скачивание видео {object_name} из MinIO в {file_path}")
        try:
            self.ensure_connection()
                
            self.client.fget_object(
                bucket_name=self.video_bucket,
                object_name=object_name,
                file_path=file_path
            )
            
            logger.info(f"Видео {object_name} успешно скачано в {file_path}")
            return True
        except S3Error as e:
            logger.error(f"Ошибка получения файла из Minio: {e}")
            return False
            
    @retry_s3_operation()
    def get_log(self, object_name):
        """Получение JSON лога из Minio"""
        logger.info(f"Получение лога {object_name} из MinIO")
        try:
            self.ensure_connection()
            
            response = self.client.get_object(
                bucket_name=self.log_bucket,
                object_name=object_name
            )
            
            data = response.read()
            log_data = json.loads(data.decode('utf-8'))
            
            logger.info(f"Лог {object_name} успешно получен из Minio")
            return log_data
        except Exception as e:
            logger.error(f"Ошибка при получении лога: {e}")
            return None
            
    @retry_s3_operation()
    def object_exists(self, bucket_name, object_name):
        """Проверка существования объекта в Minio
        
        Args:
            bucket_name (str): Имя бакета в Minio
            object_name (str): Имя объекта в Minio
            
        Returns:
            bool: True - объект существует, False - объект не существует или ошибка
        """
        logger.info(f"Проверка существования объекта {object_name} в бакете {bucket_name}")
        try:
            self.ensure_connection()
            
            self.client.stat_object(bucket_name, object_name)
            logger.info(f"Объект {object_name} существует в бакете {bucket_name}")
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"Объект {object_name} не существует в бакете {bucket_name}")
                return False
            logger.error(f"Ошибка при проверке существования объекта: {e}")
            return False
            
    @retry_s3_operation()
    def get_log_from_bucket(self, bucket_name, object_name):
        """Получение JSON лога из указанного бакета Minio
        
        Args:
            bucket_name (str): Имя бакета в Minio
            object_name (str): Имя объекта в Minio
            
        Returns:
            dict or None: JSON данные или None в случае ошибки
        """
        logger.info(f"Получение лога {object_name} из бакета {bucket_name}")
        try:
            self.ensure_connection()
                
            response = self.client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
            
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            
            response.close()
            response.release_conn()
            
            logger.info(f"Лог {object_name} успешно получен из бакета {bucket_name}")
            logger.debug(f"Размер полученных данных: {len(data)} байт")
            return json_data
        except S3Error as e:
            logger.error(f"Ошибка получения лога из Minio: {e}")
            return None
            
   
    @retry_s3_operation()
    def delete_objects(self, video_object_name, log_object_name=None):
        """Удаление видео и лога из Minio
        
        Args:
            video_object_name (str): Имя видео объекта в Minio
            log_object_name (str, optional): Имя лог объекта в Minio
            
        Returns:
            bool: True - успешно, False - ошибка
        """
        logger.info(f"Удаление объектов из MinIO: видео={video_object_name}, лог={log_object_name}")
        try:
            self.ensure_connection()
                
            self.client.remove_object(
                bucket_name=self.video_bucket,
                object_name=video_object_name
            )
            logger.info(f"Видео {video_object_name} успешно удалено")
            
            if log_object_name:
                self.client.remove_object(
                    bucket_name=self.log_bucket,
                    object_name=log_object_name
                )
                logger.info(f"Лог {log_object_name} успешно удален")
            
            return True
        except S3Error as e:
            logger.error(f"Ошибка удаления объектов из Minio: {e}")
            return False
            
    @retry_s3_operation()
    def get_presigned_url(self, object_name, expires=3600):
        """Создание временной ссылки на видео в Minio
        
        Args:
            object_name (str): Имя объекта в Minio
            expires (int, optional): Время жизни ссылки в секундах
            
        Returns:
            str or None: URL или None в случае ошибки
        """
        logger.info(f"Создание временной ссылки для {object_name} со сроком действия {expires} секунд")
        try:
            self.ensure_connection()

            try:
                self.client.stat_object(
                    bucket_name=self.video_bucket,
                    object_name=object_name
                )
            except Exception as e:
                logger.warning(f"Объект {object_name} не найден в бакете {self.video_bucket}: {e}")
                return None
            
            url = self.client.presigned_get_object(
                bucket_name=self.video_bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            
            logger.info(f"Временная ссылка для {object_name} успешно создана")
            logger.debug(f"URL: {url}")
            return url
        except S3Error as e:
            logger.error(f"Ошибка создания временной ссылки: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании временной ссылки: {e}")
            return None
            
    @retry_s3_operation()
    def list_user_videos(self, username):
        """Получение списка видео пользователя из Minio
        
        Args:
            username (str): Имя пользователя
            
        Returns:
            list: Список объектов видео
        """
        logger.info(f"Получение списка видео для пользователя {username}")
        try:
            self.ensure_connection()
                
            objects = self.client.list_objects(
                bucket_name=self.video_bucket,
                prefix=f"{username}_"
            )
            
            videos = []
            for obj in objects:
                filename = obj.object_name
                log_exists = False
                log_count = 0
                
                try:
                    log_data = self.get_log(f"{filename}.json")
                    if log_data:
                        log_exists = True
                        log_count = len(log_data)
                except Exception as e:
                    logger.warning(f"Ошибка при проверке лога для {filename}: {e}")
                
                parts = filename.split("_")
                original_name = "_".join(parts[3:]) if len(parts) > 3 else filename
                
                video_stat = self.client.stat_object(
                    bucket_name=self.video_bucket,
                    object_name=filename
                )
                
                videos.append({
                    "filename": filename,
                    "timestamp": parts[1] if len(parts) > 1 else "",
                    "original_name": original_name,
                    "has_logs": log_exists,
                    "log_count": log_count,
                    "size": video_stat.size,
                    "last_modified": video_stat.last_modified.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            result = sorted(videos, key=lambda x: x["timestamp"], reverse=True)
            logger.info(f"Найдено {len(result)} видео для пользователя {username}")
            return result
        except S3Error as e:
            logger.error(f"Ошибка получения списка видео: {e}")
            return []
