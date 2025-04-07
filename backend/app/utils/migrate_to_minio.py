#!/usr/bin/env python3
"""
Утилита для миграции существующих видео и логов из локального хранилища в MinIO.
Запускается из корня проекта командой:
python -m app.utils.migrate_to_minio
"""

import os
import json
import logging
from datetime import datetime
from app.services.minio_storage import MinioStorage
from app.services import video_storage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_to_minio():
    """Мигрирует все файлы из локального хранилища в MinIO"""
    logger.info("Начало миграции файлов в MinIO")
    
    # Инициализируем MinIO клиент
    storage = MinioStorage()
    if not storage.check_connection():
        logger.error("Не удалось подключиться к MinIO. Проверьте настройки и доступность сервера.")
        return False
    
    # Проверяем наличие директорий
    if not os.path.exists(video_storage.VIDEOS_DIR):
        logger.warning(f"Директория с видео не существует: {video_storage.VIDEOS_DIR}")
        return False
    
    if not os.path.exists(video_storage.LOGS_DIR):
        logger.warning(f"Директория с логами не существует: {video_storage.LOGS_DIR}")
        return False
    
    # Мигрируем видео
    logger.info("Миграция видеофайлов...")
    videos_migrated = 0
    logs_migrated = 0
    
    # Получаем список всех видео в MinIO для проверки дубликатов
    existing_videos = []
    try:
        # Список всех объектов в бакете videos
        objects = storage.client.list_objects(storage.video_bucket)
        existing_videos = [obj.object_name for obj in objects]
        logger.info(f"В MinIO уже есть {len(existing_videos)} видео")
    except Exception as e:
        logger.warning(f"Не удалось получить список существующих видео: {e}")
    
    for filename in os.listdir(video_storage.VIDEOS_DIR):
        if filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            # Проверяем, есть ли уже такой файл в MinIO
            if filename in existing_videos:
                logger.info(f"Пропуск {filename}: уже существует в MinIO")
                continue
            
            video_path = os.path.join(video_storage.VIDEOS_DIR, filename)
            
            # Получаем метаданные из имени файла
            parts = filename.split('_')
            if len(parts) >= 3:
                username = parts[0]
                timestamp = parts[1]
                # Оригинальное имя - все после второго подчеркивания
                original_name = '_'.join(parts[2:])
                
                # Создаем метаданные
                metadata = {
                    "username": username,
                    "original_filename": original_name,
                    "timestamp": timestamp,
                    "migrated_date": datetime.now().isoformat()
                }
                
                try:
                    # Загружаем видео в MinIO
                    logger.info(f"Миграция видео: {filename}")
                    storage.save_video(video_path, filename, metadata)
                    videos_migrated += 1
                    
                    # Проверяем наличие лога
                    log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
                    if os.path.exists(log_path):
                        # Загружаем лог
                        with open(log_path, 'r') as f:
                            log_data = json.load(f)
                        
                        logger.info(f"Миграция лога: {filename}.json")
                        storage.save_log(log_data, f"{filename}.json")
                        logs_migrated += 1
                        
                        logger.debug(f"Видео и лог для {filename} успешно мигрированы")
                    else:
                        logger.warning(f"Не найден лог для видео {filename}")
                except Exception as e:
                    logger.error(f"Ошибка при миграции {filename}: {str(e)}")
            else:
                logger.warning(f"Неверный формат имени файла: {filename}, пропуск")
    
    logger.info(f"Миграция завершена. Мигрировано {videos_migrated} видео и {logs_migrated} логов.")
    
    # Если все прошло успешно, спрашиваем пользователя, хочет ли он удалить локальные файлы
    if videos_migrated > 0 and input("Удалить локальные файлы? (y/n): ").lower() == 'y':
        delete_local_files()
    
    return True

def delete_local_files():
    """Удаляет все файлы из локального хранилища после подтверждения"""
    logger.info("Удаление локальных файлов...")
    
    # Удаляем видео
    for filename in os.listdir(video_storage.VIDEOS_DIR):
        if filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            try:
                os.remove(os.path.join(video_storage.VIDEOS_DIR, filename))
                logger.debug(f"Удален файл: {filename}")
            except Exception as e:
                logger.error(f"Ошибка при удалении {filename}: {str(e)}")
    
    # Удаляем логи
    for filename in os.listdir(video_storage.LOGS_DIR):
        if filename.endswith('.json'):
            try:
                os.remove(os.path.join(video_storage.LOGS_DIR, filename))
                logger.debug(f"Удален лог: {filename}")
            except Exception as e:
                logger.error(f"Ошибка при удалении лога {filename}: {str(e)}")
                
    logger.info("Удаление локальных файлов завершено")

if __name__ == "__main__":
    migrate_to_minio() 