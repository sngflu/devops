from datetime import datetime
import json
import os

STORAGE_DIR = "storage"
VIDEOS_DIR = os.path.join(STORAGE_DIR, "videos")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")


def init_storage():
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def save_video(video_file, username):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"{username}_{timestamp}_{video_file.filename}"
    video_path = os.path.join(VIDEOS_DIR, video_filename)
    video_file.save(video_path)
    return video_filename


def save_log(video_filename, frame_objects):
    log_filename = f"{video_filename}.json"
    log_path = os.path.join(LOGS_DIR, log_filename)
    with open(log_path, "w") as f:
        json.dump(frame_objects, f)


def get_user_videos(username):
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
    if not filename.startswith(f"{username}_"):
        return False, "Unauthorized"

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
    if not filename.startswith(f"{username}_"):
        return None

    log_path = os.path.join(LOGS_DIR, f"{filename}.json")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return json.load(f)
    return None


def rename_video(username, old_filename, new_name):
    if not old_filename.startswith(f"{username}_"):
        return False, "Unauthorized"

    try:
        parts = old_filename.split("_")
        if len(parts) < 4:
            return False, "Invalid filename format"

        new_filename = f"{parts[0]}_{parts[1]}_{parts[2]}_{new_name}"

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
