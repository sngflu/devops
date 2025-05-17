from moviepy.editor import *
from datetime import datetime
import cv2
import os
import shutil
import logging
import time
from app.models import model
from app.services.minio import MinioStorage
import tempfile
from prometheus_client import Counter, Histogram, Gauge


# Настройка логирования
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


video_directory = "runs/detect/predict/"
storage = MinioStorage()

# --- Определения метрик Prometheus для video_processing.py ---
video_processing_time_seconds = Histogram(
    'video_processing_time_seconds',
    'Time spent processing a video file',
    ['status'] # 'success' или 'error'
)

video_conversion_time_seconds = Histogram(
    'video_conversion_time_seconds',
    'Time spent converting video from AVI to MP4'
)

model_inference_time_seconds = Histogram(
    'model_inference_time_seconds',
    'Time spent on model inference for a video'
)

video_processing_errors_total = Counter(
    'video_processing_errors_total',
    'Total errors during video processing',
    ['error_type']
)

# Можно использовать Gauge для последнего обработанного разрешения или Info для общей информации
# Для примера используем Gauge, предполагая, что это может быть полезно для мониторинга типичных разрешений
# processed_video_resolution_pixels = Gauge(
#     'processed_video_resolution_pixels',
#     'Resolution (width*height) of the last processed video' 
# ) 
# Альтернатива: Гистограмма по количеству пикселей, если важнее распределение
processed_video_pixels_histogram = Histogram(
    'processed_video_pixels_histogram',
    'Distribution of processed video resolutions in total pixels (width*height)'
)

detected_objects_total = Counter(
    'detected_objects_total',
    'Total detected objects of specific types',
    ['object_type'] # e.g., 'weapon', 'knife'
)

def convert_avi_to_mp4(input_file, output_file):
    start_time = time.time()
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
        end_time = time.time()
        video_conversion_time_seconds.observe(end_time - start_time)
        return True
    except Exception as e:
        logger.error(f"Ошибка при конвертации видео: {e}")
        video_processing_errors_total.labels(error_type='conversion_failed').inc()
        # Также можно залогировать время до ошибки, если это полезно
        # end_time = time.time()
        # video_conversion_time_seconds.observe(end_time - start_time) # Опционально
        return False


def process_video(filename, confidence_threshold=0.25, username=None):
    logger.info(f"Начало обработки видео: {filename}, пользователь: {username}")
    
    # Начинаем измерение общего времени обработки
    start_time = time.time()
    
    try:
        # Проверяем и создаем директорию для сохранения результатов
        if not os.path.exists(video_directory):
            logger.info(f"Создаю директорию для результатов: {video_directory}")
            os.makedirs(video_directory, exist_ok=True)
        
        # Проверяем, что файл существует и доступен для чтения
        if not os.path.exists(filename):
            logger.error(f"Файл не найден: {filename}")
            video_processing_errors_total.labels(error_type='file_not_found').inc()
            raise FileNotFoundError(f"Видеофайл не найден: {filename}")

        cap = cv2.VideoCapture(filename)
        if not cap.isOpened():
            logger.error(f"Не удалось открыть видеофайл: {filename}")
            video_processing_errors_total.labels(error_type='file_open_failed').inc()
            raise ValueError("Не удалось открыть видеофайл. Проверьте формат файла.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        # Записываем разрешение видео в гистограмму
        pixel_count = width * height
        processed_video_pixels_histogram.observe(pixel_count)

        logger.info(
            f"Параметры видео: {total_frames} кадров, {fps} FPS, разрешение {width}x{height}"
        )

        logger.info(
            f"Запуск модели обнаружения с порогом уверенности {confidence_threshold}"
        )
        # Измеряем время инференса модели
        model_start_time = time.time()
        results = model.model(source=filename, save=True, conf=confidence_threshold, batch=16, vid_stride=8, stream=True)
        model_end_time = time.time()
        model_inference_time_seconds.observe(model_end_time - model_start_time)

        frame_objects = []
        total_weapons = 0
        total_knives = 0
        has_weapon_or_knife = False

        for i, frame_results in enumerate(results):
            boxes = frame_results.boxes
            has_weapon = False
            has_knife = False
            for box in boxes:
                cls = int(box.cls[0])
                if frame_results.names[cls] == "weapon":
                    has_weapon = True
                    total_weapons += 1
                    has_weapon_or_knife = True
                elif frame_results.names[cls] == "knife":
                    has_knife = True
                    total_knives += 1
                    has_weapon_or_knife = True
            frame_objects.append((i, has_weapon, has_knife))

        # Инкрементируем счетчики обнаруженных объектов
        if total_weapons > 0:
            detected_objects_total.labels(object_type='weapon').inc(total_weapons)
        if total_knives > 0:
            detected_objects_total.labels(object_type='knife').inc(total_knives)

        logger.info(
            f"Обнаружено объектов: {total_weapons} оружия, {total_knives} ножей"
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.basename(os.path.splitext(filename)[0])
        new_filename = f"{username}_{timestamp}_{base_filename}.mp4"
        logger.debug(f"Новое имя файла: {new_filename}")

        # Используем временную директорию для файла
        temp_dir = tempfile.gettempdir()
        final_video_path = os.path.join(temp_dir, new_filename)
        logger.debug(f"Путь к временному файлу: {final_video_path}")

        # Проверяем, создала ли модель MP4 файл
        processed_mp4 = os.path.join(
            "runs", "detect", "predict", os.path.basename(filename)[:-3] + "mp4"
        )
        processed_avi = os.path.join(
            "runs", "detect", "predict", os.path.basename(filename)[:-3] + "avi"
        )

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
                    if os.path.basename(filename).split(".")[0] in file:
                        source_path = os.path.join(video_directory, file)
                        logger.info(f"Найден альтернативный файл: {source_path}")

                        if file.endswith(".mp4"):
                            shutil.copy2(source_path, final_video_path)
                            break
                        elif file.endswith((".avi", ".mov", ".mkv")):
                            conversion_success = convert_avi_to_mp4(
                                source_path, final_video_path
                            )
                            if not conversion_success:
                                shutil.copy2(source_path, final_video_path)
                            break
                else:
                    logger.warning(
                        f"Не найдены подходящие файлы в {video_directory}. Доступные файлы: {available_files}. Создаю копию оригинала."
                    )
                    # Копируем исходный файл как результат
                    shutil.copy2(filename, final_video_path)
            else:
                logger.warning(f"Директория {video_directory} не существует. Создаю директорию и копирую оригинал.")
                os.makedirs(video_directory, exist_ok=True)
                # Копируем исходный файл как результат
                shutil.copy2(filename, final_video_path)

        # Проверяем, что файл действительно был создан и имеет ненулевой размер
        if (
            not os.path.exists(final_video_path)
            or os.path.getsize(final_video_path) == 0
        ):
            logger.warning(
                f"Финальный видеофайл не создан или имеет нулевой размер: {final_video_path}. Создаем пустой результат."
            )
            # Создаем пустое видео, чтобы не прерывать работу приложения
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{username}_{timestamp}_empty_result.mp4"
            
            # Скопируем оригинальное видео как результат
            shutil.copy2(filename, final_video_path)
            logger.info(f"Создан пустой результат (копия оригинала): {final_video_path}")

        # Создаем метаданные
        metadata = {
            "username": username,
            "original_filename": os.path.basename(filename),
            "fps": str(fps),
            "total_frames": str(total_frames),
            "width": str(width),
            "height": str(height),
            "processed_date": datetime.now().isoformat(),
        }

        # Загружаем видео в MinIO
        logger.info(f"Загрузка видео в MinIO: {new_filename}")
        storage.save_video(final_video_path, new_filename, metadata)

        # Сохраняем результаты детекции в MinIO
        # frame_objects содержит кортежи (номер_кадра, наличие_оружия, наличие_ножа)
        # где наличие_оружия и наличие_ножа - булевы значения
        log_filename = f"{new_filename}.json"
        logger.info(f"Сохранение лога детекции в MinIO: {log_filename}")
        storage.save_log(frame_objects, log_filename)

        # Очистка временных файлов модели
        logger.debug("Очистка временных файлов")
        try:
            if os.path.exists(processed_mp4):
                os.remove(processed_mp4)
            if os.path.exists(processed_avi):
                os.remove(processed_avi)
            if os.path.exists("runs"):
                shutil.rmtree("runs")
                logger.debug("Директория 'runs' удалена")
                # Создаем директорию заново, чтобы она была доступна для следующих вызовов
                os.makedirs(video_directory, exist_ok=True)
        except Exception as e:
            logger.warning(f"Ошибка при очистке временных файлов: {e}. Продолжаем выполнение.")

        # Удаление временного файла
        if os.path.exists(final_video_path):
            os.remove(final_video_path)
            logger.debug(f"Временный файл удален: {final_video_path}")

        logger.info(f"Обработка видео успешно завершена: {new_filename}")
        
        # Завершаем измерение общего времени обработки
        end_time = time.time()
        video_processing_time_seconds.labels(status='success').observe(end_time - start_time)
        
        return new_filename, frame_objects, fps, has_weapon_or_knife, log_filename

    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        
        # Завершаем измерение общего времени обработки в случае ошибки
        end_time = time.time()
        video_processing_time_seconds.labels(status='error').observe(end_time - start_time)
        
        # Инкрементируем счетчик ошибок с типом 'general_error'
        video_processing_errors_total.labels(error_type='general_error').inc()
        
        raise
