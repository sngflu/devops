import os
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)


model_path = os.environ.get("MODEL_PATH", "app/utils/yolov8nv2_e200_bs16.pt")


absolute_model_path = os.path.join(os.getcwd(), model_path)


if not os.path.exists(absolute_model_path):
    raise FileNotFoundError(f"Модель не найдена по пути: {absolute_model_path}")


model = YOLO(absolute_model_path)
logger.info(f"Модель загружена: {absolute_model_path}")



