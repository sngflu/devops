from flask import Blueprint, request, jsonify, send_from_directory
import video_processing, video_storage
import jwt
from functools import wraps
import json

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


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    print(f"Login attempt with data: {data}")
    username = data.get("username")
    password = data.get("password")

    print(f"Users config: {USERS}")
    print(f"Checking username: {username}, password: {password}")
    print(f"Username exists: {username in USERS}")
    if username in USERS:
        print(f"Stored password: {USERS[username]}")
        print(f"Password match: {USERS[username] == password}")

    if username in USERS and USERS[username] == password:
        token = jwt.encode(
            {"user": username},
            SECRET_KEY,
        )
        print(f"Generated token: {token}")
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
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            token = token.split(" ")[1]
            user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            username = user_data["user"]

            if not filename.startswith(username):
                return jsonify({"message": "Unauthorized"}), 401

            response = send_from_directory(
                video_storage.VIDEOS_DIR,
                filename,
                as_attachment=False,
                conditional=True,
            )

            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type"
            )
            response.headers["Content-Type"] = "video/mp4"

            return response
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
        except Exception as e:
            print(f"Error serving video: {e}")
            return str(e), 404

    except Exception as e:
        print(f"Error in serve_video: {e}")
        return str(e), 500


@bp.route("/videos", methods=["GET"])
@token_required
def get_videos():
    token = request.headers.get("Authorization").split(" ")[1]
    user_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    username = user_data["user"]

    videos = video_storage.get_user_videos(username)
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
