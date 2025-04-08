from flask import Blueprint, request, jsonify, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import jwt
import os
import tempfile
import logging
import uuid
import traceback
from datetime import datetime
from app.services.video_processing import video_processing
from app.services.minio import MinioStorage
from app.services.database import DatabaseManager

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


bp = Blueprint("routes", __name__, url_prefix="")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

with open(os.path.join(CONFIG_DIR, "secret.json")) as f:
    config = json.load(f)
    SECRET_KEY = config["SECRET_KEY"]

storage = MinioStorage()

db_manager = DatabaseManager()
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


@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
   

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    existing_user = db_manager.get_user_by_username(username)
    if existing_user:
        return jsonify({"message": "Username already exists"}), 400

    hashed_password = generate_password_hash(password)
    user_id, error = db_manager.create_user(username, hashed_password)
    
    if error:
        return jsonify({"message": error}), 400

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
    
    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    user = db_manager.get_user_by_username(username)
    
    if user and check_password_hash(user["password_hash"], password):
        logger.info(f"Пользователь {username} аутентифицирован")
        token = jwt.encode(
            {"user": username, "user_id": str(user["user_id"])},
            SECRET_KEY,
        )
        return jsonify({"token": token})

    logger.warning(f"Неудачная попытка входа для пользователя {username}")
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
        
    allowed_extensions = {'mp4', 'avi', 'mov', 'mkv'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        logger.warning(f"Недопустимое расширение файла: {file.filename}")
        return jsonify({"error": "Недопустимый формат файла. Разрешены только видеофайлы (.mp4, .avi, .mov, .mkv)"}), 400

    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id")  # Может отсутствовать в старых токенах
    logger.info(f"Обработка видео для пользователя: {username}")

    file_extension = os.path.splitext(file.filename)[1]
    logger.debug(f"Расширение загруженного файла: {file_extension}")

    temp_path = None
    try:
        temp_dir = tempfile.gettempdir()
        
        temp_filename = f"temp_video_{datetime.now().strftime('%Y%m%d%H%M%S')}_{username}{file_extension}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        file.save(temp_path)
        file.close()  # Убедимся, что файл закрыт
        logger.info(f"Временный файл создан: {temp_path}")
        
        if not os.path.exists(temp_path):
            logger.error(f"Временный файл не был создан: {temp_path}")
            return jsonify({"error": "Ошибка при сохранении временного файла"}), 500
            
        file_size = os.path.getsize(temp_path)
        max_size = 100 * 1024 * 1024  # 100 МБ
        if file_size > max_size:
            logger.warning(f"Файл слишком большой: {file_size//(1024*1024)} МБ")
            os.remove(temp_path)
            return jsonify({"error": f"Файл слишком большой. Максимальный размер: {max_size/(1024*1024)} МБ"}), 400
    
        confidence_threshold = 0.6
        logger.info(f"Начало обработки видео: {file.filename}, порог уверенности: {confidence_threshold}")
        video_filename, frame_objects, fps, has_weapon_or_knife, log_filename = video_processing.process_video(
            temp_path, confidence_threshold, username
        )
        
        if not video_filename or not isinstance(frame_objects, list) or not fps:
            logger.error("Некорректные результаты обработки видео")
            raise ValueError("Не удалось корректно обработать видео. Проверьте формат файла.")
        
        logger.info(f"Обработка видео завершена: {video_filename}, кадров: {len(frame_objects)}, fps: {fps}")
        
        detection_count = sum(1 for obj in frame_objects if len(obj) > 0)
        metadata = {
            "username": username,
            "original_filename": file.filename,
            "fps": str(fps),
            "detection_count": str(detection_count),
            "processed_date": datetime.now().isoformat()
        }
        logger.debug(f"Метаданные видео: {metadata}")

        if user_id:
            video_id, error = db_manager.save_video_metadata(
                user_id, 
                video_filename, 
                storage.video_bucket, 
                metadata, 
                status='completed'
            )
            success, error1 = db_manager.save_detection_results(video_id,log_filename, frame_objects, has_weapon_or_knife)
            
            if error:
                logger.error(f"Ошибка при сохранении метаданных видео в БД: {error}")
            if error1:
                logger.error(f"Ошибка при сохранении результатов обнаружения в БД: {error1}")
            else:
                db_manager.add_log(user_id, 'upload', video_id)
                
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
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.warning(f"Ошибка валидации в /predict: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
        
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
       
        logger.error(f"Ошибка в /predict: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Произошла ошибка при обработке видео. Пожалуйста, попробуйте снова или используйте другой файл."}), 500


@bp.route("/video/<path:filename>")
@token_required
def serve_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]
    user_id = user_data.get("user_id") 

    if not filename.startswith(f"{username}_"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        if user_id:
            video = db_manager.get_video_by_s3_key(filename)
            if video and str(video['user_id']) != user_id:
                return jsonify({"message": "Unauthorized"}), 401
        
        logger.info(f"Запрошено видео: {filename}")
        video_url = storage.get_presigned_url(filename)
        if video_url:
            logger.info(f"Получена временная ссылка из MinIO для {filename}")
           
            return redirect(video_url) if request.args.get('direct') else jsonify({"url": video_url}), 200
        else:
            logger.error(f"Не удалось получить временную ссылку из MinIO для {filename}")
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
        expires = int(request.args.get('expires', 3600))
        video_url = storage.get_presigned_url(filename, expires)
        if video_url:
            return jsonify({"url": video_url, "expires_in": expires}), 200
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
    user_id = user_data.get("user_id") 

    try:
        videos = []
        
        if user_id:
            db_videos = db_manager.get_user_videos(user_id)
            if db_videos:
                for video in db_videos:
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
        
        minio_videos = storage.list_user_videos(username)
        
        if minio_videos:
            db_filenames = [v['filename'] for v in videos]
            for video in minio_videos:
                if video['filename'] not in db_filenames:
                    videos.append(video)
        
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
    user_id = user_data.get("user_id") 

    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        if user_id:
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
                if str(video_data['user_id']) != user_id:
                    return jsonify({"error": "Unauthorized"}), 401
                
                detection_results = db_manager.get_video_detections(video_data['video_id'])
                if detection_results:
                    if storage.object_exists(detection_results['bucket_name'], detection_results['s3_key']):
                        logs = storage.get_log_from_bucket(detection_results['bucket_name'], detection_results['s3_key'])
                        if logs:
                            print(logs)
                            return jsonify(logs)
        
        logs = storage.get_log(f"{filename}.json")
        
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
    user_id = user_data.get("user_id") 

    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        deleted_from_db = False
        
        if user_id:
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
                success, result = db_manager.delete_video(video_data['video_id'], user_id)
                if success:
                    deleted_from_db = True
                    logger.info(f"Видео {filename} удалено из базы данных")
        
        success = storage.delete_objects(filename, f"{filename}.json")
            
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
    user_id = user_data.get("user_id") 

    data = request.get_json()
    new_name = data.get("new_name")

    if not new_name:
        return jsonify({"error": "New name is required"}), 400

    if not filename.startswith(f"{username}_"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        parts = filename.split("_")
        if len(parts) < 4:
            return jsonify({"error": "Invalid filename format"}), 400

        new_filename = f"{parts[0]}_{parts[1]}_{parts[2]}_{new_name}"
        
        updated_in_db = False
        if user_id:
            video_data = db_manager.get_video_by_s3_key(filename)
            if video_data:
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

        result = storage.rename_object(storage.video_bucket, filename, new_filename)
        
        storage.rename_object(storage.log_bucket, f"{filename}.json", f"{new_filename}.json")
            
        return jsonify({"message": "Video renamed successfully", "new_filename": new_filename})
    except Exception as e:
        logger.error(f"Ошибка при переименовании видео: {str(e)}")
        return jsonify({"error": str(e)}), 500
