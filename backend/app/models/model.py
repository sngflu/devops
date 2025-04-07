from ultralytics import YOLO
import os 
import logging

logger = logging.getLogger(__name__)

model_path = os.environ.get("MODEL_PATH", "app/utils/yolov8nv2_e200_bs16.pt")
model = YOLO(model_path)
logger.info(f"Модель загружена: {model_path}")
if not os.path.exists(model_path):
    raise FileNotFoundError(f"Модель не найдена по пути: {model_path}")



