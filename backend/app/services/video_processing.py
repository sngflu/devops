from moviepy.editor import *
from datetime import datetime
import cv2
import os
import shutil
import logging
from app.models import model
from app.services import video_storage
from app.services.minio_storage import MinioStorage
import json


# Настройка логирования
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


video_directory = "runs/detect/predict/"
storage = MinioStorage()


def convert_avi_to_mp4(input_file, output_file):
    try:
        logger.info(f"Конвертация AVI в MP4: {input_file} -> {output_file}")
        video = VideoFileClip(input_file)
        video.write_videofile(
            output_file,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
        )
        video.close()
        logger.info("Конвертация успешно завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при конвертации видео: {e}")
        return False


def process_video(filename, confidence_threshold=0.25, username=None):
    logger.info(f"Начало обработки видео: {filename}, пользователь: {username}")
    
    try:
        # Проверяем, что файл существует и доступен для чтения
        if not os.path.exists(filename):
            logger.error(f"Файл не найден: {filename}")
            raise FileNotFoundError(f"Видеофайл не найден: {filename}")
            
        cap = cv2.VideoCapture(filename)
        if not cap.isOpened():
            logger.error(f"Не удалось открыть видеофайл: {filename}")
            raise ValueError("Не удалось открыть видеофайл. Проверьте формат файла.")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        logger.info(f"Параметры видео: {total_frames} кадров, {fps} FPS, разрешение {width}x{height}")

        logger.info(f"Запуск модели обнаружения с порогом уверенности {confidence_threshold}")
        results = model.model(source=filename, save=True, conf=confidence_threshold)

        frame_objects = []
        total_weapons = 0
        total_knives = 0
        
        for i, frame_results in enumerate(results):
            boxes = frame_results.boxes
            num_weapons = 0
            num_knives = 0
            for box in boxes:
                cls = int(box.cls[0])
                if frame_results.names[cls] == "weapon":
                    num_weapons += 1
                    total_weapons += 1
                elif frame_results.names[cls] == "knife":
                    num_knives += 1
                    total_knives += 1
            frame_objects.append((i, num_weapons, num_knives))

        logger.info(f"Обнаружено объектов: {total_weapons} оружия, {total_knives} ножей")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.basename(os.path.splitext(filename)[0])
        new_filename = f"{username}_{timestamp}_{base_filename}.mp4"
        logger.debug(f"Новое имя файла: {new_filename}")
        
        # Всегда сохраняем в локальное хранилище временно
        os.makedirs(video_storage.VIDEOS_DIR, exist_ok=True)
        final_video_path = os.path.join(video_storage.VIDEOS_DIR, new_filename)
        logger.debug(f"Путь к временному файлу: {final_video_path}")

        # Проверяем, создала ли модель MP4 файл
        processed_mp4 = os.path.join("runs", "detect", "predict", os.path.basename(filename)[:-3] + "mp4")
        processed_avi = os.path.join("runs", "detect", "predict", os.path.basename(filename)[:-3] + "avi")
        
        if os.path.exists(processed_mp4):
            # Если модель создала MP4, просто копируем его
            logger.info(f"Найден MP4 файл, копирование: {processed_mp4}")
            shutil.copy2(processed_mp4, final_video_path)
        elif os.path.exists(processed_avi):
            # Если модель создала AVI, конвертируем в MP4
            logger.info(f"Найден AVI файл, конвертация: {processed_avi}")
            conversion_success = convert_avi_to_mp4(processed_avi, final_video_path)
            if not conversion_success:
                logger.warning("Конвертация не удалась, пробуем прямое копирование...")
                shutil.copy2(processed_avi, final_video_path)
        else:
            # Ищем любые созданные файлы в директории predict
            available_files = []
            if os.path.exists(video_directory):
                available_files = os.listdir(video_directory)
                
                # Ищем файл с похожим именем
                for file in available_files:
                    if os.path.basename(filename).split('.')[0] in file:
                        source_path = os.path.join(video_directory, file)
                        logger.info(f"Найден альтернативный файл: {source_path}")
                        
                        if file.endswith('.mp4'):
                            shutil.copy2(source_path, final_video_path)
                            break
                        elif file.endswith(('.avi', '.mov', '.mkv')):
                            conversion_success = convert_avi_to_mp4(source_path, final_video_path)
                            if not conversion_success:
                                shutil.copy2(source_path, final_video_path)
                            break
                else:
                    logger.error(f"Не найдены подходящие файлы в {video_directory}. Доступные файлы: {available_files}")
                    raise FileNotFoundError(f"Обработанное видео не найдено в директории {video_directory}")
            else:
                logger.error(f"Директория {video_directory} не существует")
                raise FileNotFoundError(f"Директория {video_directory} не найдена")

        # Проверяем, что файл действительно был создан и имеет ненулевой размер
        if not os.path.exists(final_video_path) or os.path.getsize(final_video_path) == 0:
            logger.error(f"Финальный видеофайл не создан или имеет нулевой размер: {final_video_path}")
            raise FileNotFoundError("Ошибка создания обработанного видео")

        # Создаем метаданные
        metadata = {
            "username": username,
            "original_filename": os.path.basename(filename),
            "fps": str(fps),
            "total_frames": str(total_frames),
            "width": str(width),
            "height": str(height),
            "processed_date": datetime.now().isoformat()
        }

        # Загружать видео в MinIO будем в маршруте /predict, здесь только подготавливаем файл
        logger.info(f"Видео подготовлено: {new_filename}")

        # Очистка временных файлов модели, не трогаем финальный файл
        logger.debug("Очистка временных файлов")
        if os.path.exists(processed_mp4):
            os.remove(processed_mp4)
        if os.path.exists(processed_avi):
            os.remove(processed_avi)
        if os.path.exists("runs"):
            shutil.rmtree("runs")
            logger.debug("Директория 'runs' удалена")

        logger.info(f"Обработка видео успешно завершена: {new_filename}")
        return new_filename, frame_objects, fps
    
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def delete_folder_contents(folder_path):
    logger.info(f"Очистка содержимого папки: {folder_path}")
    try:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Файл удален: {file_path}")
                elif os.path.isdir(file_path):
                    delete_folder_contents(file_path)
                    os.rmdir(file_path)
                    logger.debug(f"Директория удалена: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении {file_path}: {e}")
        logger.info(f"Очистка папки {folder_path} завершена")
    except Exception as e:
        logger.error(f"Ошибка при очистке папки {folder_path}: {e}")
