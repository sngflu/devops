from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import jwt
import os
import video_processing, video_storage


bp = Blueprint("routes", __name__, url_prefix="")

with open("config/secret.json") as f:
    config = json.load(f)
    SECRET_KEY = config["SECRET_KEY"]

with open("config/users.json") as f:
    user_config = json.load(f)
    USERS = user_config["users"]


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
    with open("config/users.json", "w") as f:
        json.dump({"users": USERS}, f, indent=2)


@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    if username in USERS:
        return jsonify({"message": "Username already exists"}), 400

    hashed_password = generate_password_hash(password)
    USERS[username] = hashed_password
    save_users()

    token = jwt.encode(
        {"user": username},
        SECRET_KEY,
    )

    return jsonify({"token": token}), 201


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

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
    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    filename = file.filename
    file.save(filename)

    confidence_threshold = 0.6
    video_filename, frame_objects, fps = video_processing.process_video(
        filename, confidence_threshold, username
    )

    return (
        jsonify(
            {"video_url": video_filename, "frame_objects": frame_objects, "fps": fps}
        ),
        200,
    )


@bp.route("/video/<path:filename>")
@token_required
def serve_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    if not filename.startswith(f"{username}_"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        # Проверяем, используется ли Minio
        if video_storage.is_minio_enabled():
            # Если используется Minio, возвращаем временную ссылку
            video_url = video_storage.get_video_path(filename)
            if video_url:
                # Делаем редирект на временную ссылку
                return jsonify({"url": video_url}), 200
            else:
                return jsonify({"message": "Video not found in Minio"}), 404
        else:
            # Иначе отдаем файл из локального хранилища
            response = send_from_directory(
                video_storage.VIDEOS_DIR,
                filename,
                as_attachment=False,
                conditional=True,
            )
            return response
    except Exception as e:
        return str(e), 404

    except Exception as e:
        print(f"Error in serve_video: {e}")
        return str(e), 500


@bp.route("/video/<path:filename>/url")
@token_required
def get_video_url(filename):
    """Получить временную ссылку на видео из Minio"""
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    if not filename.startswith(f"{username}_"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        if video_storage.is_minio_enabled():
            # Получаем временную ссылку на видео из Minio
            video_url = video_storage.get_video_path(filename)
            if video_url:
                return jsonify({"url": video_url}), 200
            else:
                return jsonify({"message": "Video not found in Minio"}), 404
        else:
            # Если Minio не используется, возвращаем локальный URL
            return jsonify({"url": f"/video/{filename}"}), 200
    except Exception as e:
        print(f"Error in get_video_url: {e}")
        return str(e), 500


@bp.route("/videos", methods=["GET"])
@token_required
def get_videos():
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    videos = []
    for filename in os.listdir(video_storage.VIDEOS_DIR):
        if filename.startswith(f"{username}_"):
            log_path = os.path.join(video_storage.LOGS_DIR, f"{filename}.json")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    logs = json.load(f)
                    log_count = sum(1 for log in logs if log[1] > 0 or log[2] > 0)

                original_name = "_".join(filename.split("_")[3:])
                videos.append(
                    {
                        "filename": filename,
                        "original_name": original_name,
                        "log_count": log_count,
                    }
                )

    return jsonify(videos)


@bp.route("/videos/<filename>/logs", methods=["GET"])
@token_required
def get_video_logs(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    logs = video_storage.get_video_logs(username, filename)
    if logs is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(logs)


@bp.route("/videos/<filename>", methods=["DELETE"])
@token_required
def delete_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    success, message = video_storage.delete_video(username, filename)
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message})


@bp.route("/videos/<filename>", methods=["PUT"])
@token_required
def update_video(filename):
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    data = request.get_json()
    new_name = data.get("new_name")

    if not new_name:
        return jsonify({"error": "New name is required"}), 400

    success, message = video_storage.rename_video(username, filename, new_name)
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message, "new_filename": message})
