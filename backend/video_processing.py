import cv2
import os
from moviepy.editor import *
import model
from datetime import datetime
import video_storage
import shutil


video_directory = "runs/detect/predict/"


def convert_avi_to_mp4(input_file, output_file):
    try:
        video = VideoFileClip(input_file)

        video.write_videofile(
            output_file,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
        )
        video.close()
        return True
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


def process_video(filename, confidence_threshold=0.25, username=None):
    cap = cv2.VideoCapture(filename)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    cap.release()

    results = model.model(source=filename, save=True, conf=confidence_threshold)

    frame_objects = []
    for i, frame_results in enumerate(results):
        boxes = frame_results.boxes
        num_weapons = 0
        num_knives = 0
        for box in boxes:
            cls = int(box.cls[0])
            if frame_results.names[cls] == "weapon":
                num_weapons += 1
            elif frame_results.names[cls] == "knife":
                num_knives += 1
        frame_objects.append((i, num_weapons, num_knives))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = os.path.splitext(filename)[0]
    new_filename = f"{username}_{timestamp}_{base_filename}.mp4"

    processed_avi = os.path.join("runs", "detect", "predict", filename[:-3] + "avi")
    final_video_path = os.path.join(video_storage.VIDEOS_DIR, new_filename)

    conversion_success = convert_avi_to_mp4(processed_avi, final_video_path)

    if not conversion_success:
        print("Conversion failed, trying direct copy...")
        shutil.copy2(processed_avi, final_video_path)

    video_storage.save_log(new_filename, frame_objects)

    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(processed_avi):
        os.remove(processed_avi)
    if os.path.exists(video_directory):
        shutil.rmtree("runs")

    return new_filename, frame_objects, fps


def delete_folder_contents(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                delete_folder_contents(file_path)
                os.rmdir(file_path)
        except Exception as e:
            print(e)
