from flask import Blueprint, request, jsonify, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import jwt
import os
import tempfile
import logging
import uuid
from datetime import datetime
from app.services import video_processing, video_storage
from app.services.minio_storage import MinioStorage
from app.services.database import db_manager


# Настройка логирования
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


bp = Blueprint("routes", __name__, url_prefix="")

# Используем абсолютные пути к конфигурационным файлам
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

with open(os.path.join(CONFIG_DIR, "secret.json")) as f:
    config = json.load(f)
    SECRET_KEY = config["SECRET_KEY"]

with open(os.path.join(CONFIG_DIR, "users.json")) as f:
    user_config = json.load(f)
    USERS = user_config["users"]

# Инициализируем объект для работы с MinIO
storage = MinioStorage()

# Инициализация базы данных
db_manager.init_database()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"message": "Token is missing"}), 401
        try:
            token = token.split(" ")[1]
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except:
            return jsonify({"message": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated


def save_users():
    with open(os.path.join(CONFIG_DIR, "users.json"), "w") as f:
        json.dump({"users": USERS}, f, indent=2)


@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    #email = data.get("email", "")  # Email может быть опциональным

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    # Проверяем, существует ли пользователь в базе данных
    existing_user = db_manager.get_user_by_username(username)
    if existing_user:
        return jsonify({"message": "Username already exists"}), 400

    # Хешируем пароль и создаем пользователя
    hashed_password = generate_password_hash(password)
    user_id, error = db_manager.create_user(username, hashed_password)
    
    if error:
        return jsonify({"message": error}), 400

    # Генерируем JWT токен
    token = jwt.encode(
        {"user": username, "user_id": str(user_id)},
        SECRET_KEY,
    )

    return jsonify({"token": token}), 201


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # Проверяем, существует ли пользователь в базе данных
    user = db_manager.get_user_by_username(username)
    
    if user and check_password_hash(user["password_hash"], password):
        # Генерируем JWT токен с ID пользователя
        token = jwt.encode(
            {"user": username, "user_id": str(user["user_id"])},
            SECRET_KEY,
        )
        return jsonify({"token": token})

    # Для обратной совместимости проверяем локальных пользователей
    if username in USERS and check_password_hash(USERS[username], password):
        token = jwt.encode(
            {"user": username},
            SECRET_KEY,
        )
        return jsonify({"token": token})

    return jsonify({"message": "Invalid credentials"}), 401


@bp.route("/predict", methods=["POST"])
@token_required
def processing():
    logger.info("Получен запрос на обработку видео")
    
    if "file" not in request.files:
        logger.warning("Запрос не содержит файла")
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.warning("Файл не выбран")
        return jsonify({"error": "No selected file"}), 400
        
    # Проверка расширения файла
    allowed_extensions = {'mp4', 'avi', 'mov', 'mkv'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        logger.warning(f"Недопустимое расширение файла: {file.filename}")
        return jsonify({"error": "Недопустимый формат файла. Разрешены только видеофайлы (.mp4, .avi, .mov, .mkv)"}), 400

    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах
    logger.info(f"Обработка видео для пользователя: {username}")

    # Получаем расширение файла
    file_extension = os.path.splitext(file.filename)[1]
    logger.debug(f"Расширение загруженного файла: {file_extension}")

    # Создаем временный файл для обработки
    temp_path = None
    try:
        # Создаем временный каталог, если его нет
        temp_dir = tempfile.gettempdir()
        # Создаем уникальное имя файла с сохранением расширения
        temp_filename = f"temp_video_{datetime.now().strftime('%Y%m%d%H%M%S')}_{username}{file_extension}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Сохраняем файл с правильным расширением
        file.save(temp_path)
        file.close()  # Убедимся, что файл закрыт
        logger.info(f"Временный файл создан: {temp_path}")
        
        # Проверяем, что файл действительно существует
        if not os.path.exists(temp_path):
            logger.error(f"Временный файл не был создан: {temp_path}")
            return jsonify({"error": "Ошибка при сохранении временного файла"}), 500
            
        # Проверка размера файла
        file_size = os.path.getsize(temp_path)
        max_size = 100 * 1024 * 1024  # 100 МБ
        if file_size > max_size:
            logger.warning(f"Файл слишком большой: {file_size//(1024*1024)} МБ")
            os.remove(temp_path)
            return jsonify({"error": f"Файл слишком большой. Максимальный размер: {max_size/(1024*1024)} МБ"}), 400
        
        # Проверка существования директорий для хранения файлов
        if not os.path.exists(video_storage.VIDEOS_DIR):
            logger.info(f"Создание директории для видео: {video_storage.VIDEOS_DIR}")
            os.makedirs(video_storage.VIDEOS_DIR, exist_ok=True)
        if not os.path.exists(video_storage.LOGS_DIR):
            logger.info(f"Создание директории для логов: {video_storage.LOGS_DIR}")
            os.makedirs(video_storage.LOGS_DIR, exist_ok=True)
    
        # Обрабатываем видео
        confidence_threshold = 0.6
        logger.info(f"Начало обработки видео: {file.filename}, порог уверенности: {confidence_threshold}")
        video_filename, frame_objects, fps = video_processing.process_video(
            temp_path, confidence_threshold, username
        )
        
        # Проверка результатов обработки
        if not video_filename or not isinstance(frame_objects, list) or not fps:
            logger.error("Некорректные результаты обработки видео")
            raise ValueError("Не удалось корректно обработать видео. Проверьте формат файла.")
        
        logger.info(f"Обработка видео завершена: {video_filename}, кадров: {len(frame_objects)}, fps: {fps}")
        
        # Метаданные для видео
        detection_count = sum(1 for obj in frame_objects if len(obj) > 0)
        metadata = {
            "username": username,
            "original_filename": file.filename,
            "fps": str(fps),
            "detection_count": str(detection_count),
            "processed_date": datetime.now().isoformat()
        }
        logger.debug(f"Метаданные видео: {metadata}")

        # Сохраняем обработанное видео в MinIO
        local_path = os.path.join(video_storage.VIDEOS_DIR, video_filename)
        logger.debug(f"Проверка локального пути: {local_path}")
        
        if not os.path.exists(local_path):
            logger.error(f"Локальный файл не найден после обработки: {local_path}")
            return jsonify({"error": "Ошибка при обработке видео: файл не найден"}), 500
            
        if os.path.getsize(local_path) == 0:
            logger.error(f"Обработанный файл имеет нулевой размер: {local_path}")
            return jsonify({"error": "Ошибка при обработке видео: файл пуст"}), 500
            
        try:
            logger.info(f"Сохранение видео в MinIO: {video_filename}")
            storage.save_video(local_path, video_filename, metadata)
            
            # Сохраняем результаты детекции
            if frame_objects:
                logger.info(f"Сохранение лога детекции в MinIO: {video_filename}.json")
                storage.save_log(frame_objects, f"{video_filename}.json")
                
            # Также сохраняем логи локально для обратной совместимости
            log_path = os.path.join(video_storage.LOGS_DIR, f"{video_filename}.json")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "w") as f:
                json.dump(frame_objects, f)
                
            # Если у нас есть ID пользователя, сохраняем в базу данных
            if user_id:
                # Сохраняем метаданные видео в БД
                video_id, error = db_manager.save_video_metadata(
                    user_id, 
                    video_filename, 
                    storage.video_bucket, 
                    metadata, 
                    status='completed'
                )
                
                if error:
                    logger.error(f"Ошибка при сохранении метаданных видео в БД: {error}")
                else:
                    # Сохраняем результаты обнаружения
                    success, error = db_manager.save_detection_results(video_id, frame_objects)
                    if not success:
                        logger.error(f"Ошибка при сохранении результатов обнаружения в БД: {error}")
                    
                    # Добавляем запись в журнал действий
                    db_manager.add_log(user_id, 'upload', video_id)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении в MinIO: {str(e)}")
            # Оставляем локальный файл на случай ошибки MinIO
            logger.warning("Видео сохранено только локально из-за ошибки MinIO")
                
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"Временный файл удален: {temp_path}")

        logger.info(f"Запрос /predict успешно обработан для файла: {file.filename}")
        return jsonify({
            "video_url": video_filename, 
            "frame_objects": frame_objects, 
            "fps": fps
        }), 200
    
    except ValueError as ve:
        # Обработка ошибок валидации
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.warning(f"Ошибка валидации в /predict: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
        
    except Exception as e:
        # Удаляем временный файл в случае ошибки
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        # Вывод полной информации об ошибке для отладки
        import traceback
        logger.error(f"Ошибка в /predict: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Произошла ошибка при обработке видео. Пожалуйста, попробуйте снова или используйте другой файл."}), 500


@bp.route("/video/<path:filename>")
@token_required
def serve_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах

    # Проверка прав доступа
    if not filename.startswith(f"{username}_"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        # Проверяем наличие видео в базе данных
        if user_id:
            video = db_manager.get_video_by_s3_key(filename)
            if video and str(video['user_id']) != user_id:
                return jsonify({"message": "Unauthorized"}), 401
        
        # Возвращаем временную ссылку из MinIO
        logger.info(f"Запрошено видео: {filename}")
        video_url = storage.get_presigned_url(filename)
        if video_url:
            logger.info(f"Получена временная ссылка из MinIO для {video_url}")
           
            return redirect(video_url) if request.args.get('direct') else jsonify({"url": video_url}), 200
        else:
            logger.warning(f"Не удалось получить временную ссылку из MinIO для {filename}, проверяем локальное хранилище")
            # Если файл не найден в MinIO, проверяем локальное хранилище
            # (для обратной совместимости)
            local_path = os.path.join(video_storage.VIDEOS_DIR, filename)
            if os.path.exists(local_path):
                logger.info(f"Файл найден в локальном хранилище: {local_path}")
                if os.path.getsize(local_path) > 0:
                    response = send_from_directory(
                        video_storage.VIDEOS_DIR,
                        filename,
                        as_attachment=False,
                        conditional=True,
                    )
                    return response
                else:
                    logger.error(f"Локальный файл имеет нулевой размер: {local_path}")
                    return jsonify({"error": "Файл поврежден (нулевой размер)"}), 500
            else:
                logger.error(f"Видео не найдено ни в MinIO, ни в локальном хранилище: {filename}")
                return jsonify({"error": "Video not found"}), 404
    except Exception as e:
        logger.error(f"Ошибка при получении видео: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@bp.route("/video/<path:filename>/url")
@token_required
def get_video_url(filename):
    """Получить временную ссылку на видео из MinIO"""
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    if not filename.startswith(f"{username}_"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        # Получаем URL с настраиваемым сроком действия
        expires = int(request.args.get('expires', 3600))  # По умолчанию 1 час
        video_url = storage.get_presigned_url(filename, expires)
        if video_url:
            return jsonify({"url": video_url, "expires_in": expires}), 200
        else:
            # Если не найдено в MinIO, проверяем локальное хранилище для обратной совместимости
            if os.path.exists(os.path.join(video_storage.VIDEOS_DIR, filename)):
                return jsonify({"url": f"/video/{filename}"}), 200
            else:
                return jsonify({"error": "Video not found"}), 404
    except Exception as e:
        logger.error(f"Ошибка при получении URL видео: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route("/videos", methods=["GET"])
@token_required
def get_videos():
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах

    try:
        videos = []
        
        # Если у нас есть ID пользователя, получаем видео из БД
        if user_id:
            db_videos = db_manager.get_user_videos(user_id)
            if db_videos:
                for video in db_videos:
                    # Формируем данные для ответа
                    s3_key = video['s3_key']
                    original_name = "_".join(s3_key.split("_")[3:]) if s3_key.count("_") >= 3 else s3_key
                    
                    videos.append({
                        "filename": s3_key,
                        "original_name": original_name,
                        "upload_time": video['upload_time'].isoformat(),
                        "status": video['status'],
                        "video_id": str(video['video_id']),
                        "weapon_detected": video.get('weapon_detected', False)
                    })
        
        # Получаем список видео из MinIO для объединения результатов или если нет ID пользователя
        minio_videos = storage.list_user_videos(username)
        
        # Проверяем, что видео из MinIO уже не включены в результаты из БД
        if minio_videos:
            db_filenames = [v['filename'] for v in videos]
            for video in minio_videos:
                if video['filename'] not in db_filenames:
                    videos.append(video)
        
        # Если список пустой, проверяем локальное хранилище для обратной совместимости
        if not videos and os.path.exists(video_storage.VIDEOS_DIR):
            local_videos = []
            for filename in os.listdir(video_storage.VIDEOS_DIR):
                if filename.startswith(f"{username}_"):
                    log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
                    log_count = 0
                    
                    if os.path.exists(log_path):
                        with open(log_path, "r") as f:
                            logs = json.load(f)
                            log_count = sum(1 for log in logs if log[1] > 0 or log[2] > 0)

                    original_name = "_".join(filename.split("_")[3:])
                    local_videos.append(
                        {
                            "filename": filename,
                            "original_name": original_name,
                            "log_count": log_count,
                        }
                    )
            if local_videos:
                videos = local_videos
                logger.info(f"Найдено {len(videos)} видео в локальном хранилище для пользователя {username}")
        
        return jsonify(videos)
    except Exception as e:
        logger.error(f"Ошибка при получении списка видео: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route("/videos/<filename>/logs", methods=["GET"])
@token_required
def get_video_logs(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах

    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Если у нас есть ID пользователя, пробуем получить результаты из БД
        if user_id:
            # Находим видео по ключу S3
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
                # Проверяем, что видео принадлежит пользователю
                if str(video_data['user_id']) != user_id:
                    return jsonify({"error": "Unauthorized"}), 401
                
                # Получаем результаты обнаружения из БД
                detection_results = db_manager.get_video_detections(video_data['video_id'])
                if detection_results:
                    # Преобразуем результаты в формат, ожидаемый фронтендом
                    logs = []
                    detections = detection_results.get('detections', [])
                    
                    # Группируем обнаружения по кадрам
                    frame_detections = {}
                    for detect in detections:
                        frame_num = detect['frame_number']
                        if frame_num not in frame_detections:
                            frame_detections[frame_num] = [detect['timestamp']]
                        
                        frame_detections[frame_num].append([
                            detect['weapon_type'],
                            detect['confidence']
                        ])
                    
                    # Создаем последовательность кадров
                    max_frame = max(frame_detections.keys()) if frame_detections else 0
                    for i in range(max_frame + 1):
                        if i in frame_detections:
                            logs.append(frame_detections[i])
                        else:
                            logs.append([])
                    
                    return jsonify(logs)
        
        # Получаем логи из MinIO
        logs = storage.get_log(f"{filename}.json")
        
        # Если логи не найдены в MinIO, проверяем локальное хранилище
        if logs is None and os.path.exists(video_storage.LOGS_DIR):
            log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    logs = json.load(f)
        
        if logs is None:
            return jsonify({"error": "Logs not found"}), 404
            
        return jsonify(logs)
    except Exception as e:
        logger.error(f"Ошибка при получении логов видео: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route("/videos/<filename>", methods=["DELETE"])
@token_required
def delete_video_route(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах

    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        deleted_from_db = False
        
        # Если есть ID пользователя, пробуем удалить из БД
        if user_id:
            # Сначала находим видео по ключу S3
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
                # Удаляем видео из БД
                success, result = db_manager.delete_video(video_data['video_id'], user_id)
                if success:
                    deleted_from_db = True
                    logger.info(f"Видео {filename} удалено из базы данных")
        
        # Удаляем видео и логи из MinIO
        success = storage.delete_objects(filename, f"{filename}.json")
        
        # Также удаляем из локального хранилища, если файлы есть
        # (для обратной совместимости)
        video_path = os.path.join(video_storage.VIDEOS_DIR, filename)
        log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
        
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(log_path):
            os.remove(log_path)
            
        if not success and not deleted_from_db:
            # Если удаление из MinIO не удалось, но из локального хранилища удалили
            if not (os.path.exists(video_path) or os.path.exists(log_path)):
                success = True
                
        if not success and not deleted_from_db:
            return jsonify({"error": "Failed to delete video"}), 500
            
        return jsonify({"message": "Successfully deleted"})
    except Exception as e:
        logger.error(f"Ошибка при удалении видео: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route("/videos/<filename>", methods=["PUT"])
@token_required
def update_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах

    data = request.get_json()
    new_name = data.get("new_name")

    if not new_name:
        return jsonify({"error": "New name is required"}), 400

    # Проверка прав доступа
    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        parts = filename.split("_")
        if len(parts) < 4:
            return jsonify({"error": "Invalid filename format"}), 400

        new_filename = f"{parts[0]}_{parts[1]}_{parts[2]}_{new_name}"
        
        # Если у нас есть ID пользователя, обновляем в базе данных
        updated_in_db = False
        if user_id:
            # Находим видео по ключу S3
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
                # Используем новый метод для переименования видео в БД
                success, error = db_manager.rename_video(
                    video_data['video_id'], 
                    user_id, 
                    new_filename
                )
                
                if success:
                    updated_in_db = True
                    logger.info(f"Обновлено имя видео в БД: {filename} -> {new_filename}")
                else:
                    logger.error(f"Ошибка при обновлении имени видео в БД: {error}")

        # Переименовываем объект в MinIO
        result = storage.rename_object(storage.video_bucket, filename, new_filename)
        
        # Также переименовываем логи, если они существуют
        storage.rename_object(storage.log_bucket, f"{filename}.json", f"{new_filename}.json")
        
        # Для обратной совместимости также переименовываем локальные файлы
        video_path = os.path.join(video_storage.VIDEOS_DIR, filename)
        new_video_path = os.path.join(video_storage.VIDEOS_DIR, new_filename)
        log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
        new_log_path = os.path.join(video_storage.LOGS_DIR, f"{new_filename}.json")
        
        if os.path.exists(video_path):
            os.rename(video_path, new_video_path)
        if os.path.exists(log_path):
            os.rename(log_path, new_log_path)
            
        return jsonify({"message": "Video renamed successfully", "new_filename": new_filename})
    except Exception as e:
        logger.error(f"Ошибка при переименовании видео: {str(e)}")
        return jsonify({"error": str(e)}), 500
