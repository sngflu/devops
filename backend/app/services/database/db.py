import os
import json
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from contextlib import contextmanager

register_uuid()

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class DatabaseManager:
    """Класс для управления подключением к базе данных и операциями с ней"""
    
    def __init__(self, config=None):
        """Инициализация менеджера базы данных"""
        self.db_config = config or {
            'dbname': os.environ.get('DB_NAME', 'pgdatabase'),
            'user': os.environ.get('DB_USER', 'pguser'),
            'password': os.environ.get('DB_PASSWORD', 'pgpassword'),
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': os.environ.get('DB_PORT', '5432')
        }

    def get_connection(self):
        """Получение соединения с базой данных"""
        try:
            conn = psycopg2.connect(
                dbname=self.db_config['dbname'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                host=self.db_config['host'],
                port=self.db_config['port']
            )
            return conn
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            return None
    
    @contextmanager
    def transaction(self):
        """
        Контекстный менеджер для работы с транзакциями.
        
        Пример использования:
        with db_manager.transaction() as cursor:
            cursor.execute("INSERT INTO ...")
            cursor.execute("UPDATE ...")
        # Транзакция будет автоматически зафиксирована при выходе из блока with
        # При возникновении исключения транзакция будет отменена
        """
        conn = self.get_connection()
        if not conn:
            raise Exception("Не удалось установить соединение с базой данных")
            
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка транзакции: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация базы данных при первом запуске"""
        logger.info("Проверка соединения с базой данных...")
        conn = self.get_connection()
        if not conn:
            logger.error("Не удалось подключиться к базе данных")
            return False
        
        logger.info("Соединение с базой данных установлено успешно")
        conn.close()
        return True
    
    def execute_query(self, query, params=None, fetch=None, cursor_factory=None):
        """
        Выполнение запроса к базе данных
        
        :param query: SQL запрос
        :param params: Параметры для SQL запроса
        :param fetch: тип выборки ('one', 'all', 'none')
        :param cursor_factory: Фабрика для курсора
        :return: Результат запроса или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None, "Ошибка подключения к БД"
        
        try:
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                cur.execute(query, params or ())
                
                if fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'all':
                    result = cur.fetchall()
                else:
                    result = None
                
                # Применяем изменения если это не SELECT
                if not query.strip().upper().startswith("SELECT"):
                    conn.commit()
                    
                return result, None
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return None, "Нарушение ограничения уникальности"
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка выполнения запроса: {e}")
            return None, f"Ошибка выполнения запроса: {e}"
        finally:
            conn.close()
    
    
    def get_user_by_username(self, username):
        """Получение пользователя по имени пользователя"""
        result, error = self.execute_query(
            """SELECT * FROM users WHERE username = %s""",
            (username,),
            fetch='one',
            cursor_factory=RealDictCursor
        )
        
        return result
    
    def create_user(self, username, password_hash, role='user'):
        """Создание нового пользователя"""
        result, error = self.execute_query(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING user_id
            """,
            (username, password_hash, role),
            fetch='one',
            cursor_factory=RealDictCursor
        )
        
        if error:
            if "уникальности" in error:
                return None, "Пользователь с таким именем уже существует"
            return None, error
        
        logger.info(f"Создан новый пользователь: {username}")
        return result['user_id'], None
    
    def save_video_metadata(self, user_id, s3_key, bucket_name, metadata=None, status='pending'):
        """Сохранение метаданных видео в базе данных"""
        if metadata is None:
            metadata = {}
        
        result, error = self.execute_query(
            """
            INSERT INTO videos (user_id, s3_key, bucket_name, status, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING video_id
            """,
            (user_id, s3_key, bucket_name, status, json.dumps(metadata)),
            fetch='one',
            cursor_factory=RealDictCursor
        )
        
        if error:
            return None, error
        
        logger.info(f"Сохранены метаданные видео: {s3_key}")
        return result['video_id'], None
    
    def update_video_status(self, video_id, status):
        """Обновление статуса обработки видео"""
        _, error = self.execute_query(
            """
            UPDATE videos 
            SET status = %s
            WHERE video_id = %s
            """,
            (status, video_id),
            fetch=None
        )
        
        if error:
            return False, error
        
        logger.info(f"Обновлен статус видео {video_id} на {status}")
        return True, None
    
    def rename_video(self, video_id, user_id, new_s3_key):
        """
        Переименование видео (обновление ключа S3)
        
        :param video_id: ID видео в базе данных
        :param user_id: ID пользователя для проверки и логирования
        :param new_s3_key: Новый ключ S3
        :return: (успех, сообщение об ошибке)
        """
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    """
                    SELECT s3_key FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """, 
                    (video_id, user_id)
                )
                
                video = cursor.fetchone()
                if not video:
                    return False, "Видео не найдено или нет доступа"
                
                old_s3_key = video['s3_key']
                
                log_details = {
                    'old_s3_key': old_s3_key,
                    'new_s3_key': new_s3_key
                }
                cursor.execute(
                    """
                    INSERT INTO logs (user_id, action, video_id, details)
                    VALUES (%s, %s, %s, %s)
                    """, 
                    (user_id, 'rename', video_id, json.dumps(log_details))
                )
                
                cursor.execute(
                    """
                    UPDATE videos 
                    SET s3_key = %s
                    WHERE video_id = %s
                    """, 
                    (new_s3_key, video_id)
                )
                
            logger.info(f"Обновлено имя видео: {old_s3_key} -> {new_s3_key}")
            return True, None
            
        except Exception as e:
            logger.error(f"Ошибка при переименовании видео: {e}")
            return False, f"Ошибка при переименовании видео: {e}"
    
    def get_user_videos(self, user_id):
        """Получение списка видео пользователя"""
        result, error = self.execute_query(
            """
            SELECT v.*, 
                   CASE WHEN dr.weapon_detected THEN true ELSE false END as weapon_detected,
                   dr.result_id
            FROM videos v
            LEFT JOIN detection_results dr ON v.video_id = dr.video_id
            WHERE v.user_id = %s
            ORDER BY v.upload_time DESC
            """,
            (user_id,),
            fetch='all',
            cursor_factory=RealDictCursor
        )
        
        return result or []
    
    def get_video_by_s3_key(self, s3_key):
        """Получение видео по ключу S3"""
        result, _ = self.execute_query(
            """
            SELECT * FROM videos 
            WHERE s3_key = %s
            """,
            (s3_key,),
            fetch='one',
            cursor_factory=RealDictCursor
        )
        
        return result
    
    def delete_video(self, video_id, user_id):
        """Удаление видео из базы данных"""
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    """
                    SELECT s3_key, bucket_name FROM videos 
                    WHERE video_id = %s AND user_id = %s
                    """, 
                    (video_id, user_id)
                )
                
                video = cursor.fetchone()
                if not video:
                    return False, "Видео не найдено или нет доступа"
                
                log_details = {
                    's3_key': video['s3_key'],
                    'bucket_name': video['bucket_name']
                }
                cursor.execute(
                    """
                    INSERT INTO logs (user_id, action, video_id, details)
                    VALUES (%s, %s, %s, %s)
                    """, 
                    (user_id, 'delete', video_id, json.dumps(log_details))
                )
                
                # После логирования выполняем удаление видео
                cursor.execute(
                    """
                    DELETE FROM videos 
                    WHERE video_id = %s
                    """, 
                    (video_id,)
                )
                
            logger.info(f"Удалено видео: {video['s3_key']}")
            return True, video  # Возвращаем данные о видео
            
        except Exception as e:
            logger.error(f"Ошибка при удалении видео: {e}")
            return False, f"Ошибка при удалении видео: {e}"
    
    def save_detection_results(self, video_id, log_filename, frame_objects, weapon_detected, summary=None):
        """Сохранение результатов обнаружения оружия"""
        conn = self.get_connection()
        if not conn:
            return False, "Ошибка подключения к БД"
        

        if summary is None:
            summary = {
                'total_frames': len(frame_objects),
                'detection_frames': sum(1 for frame in frame_objects if len(frame) > 0)
            }
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                SELECT user_id, s3_key, bucket_name FROM videos
                WHERE video_id = %s
                """, (video_id,))
                
                video_data = cur.fetchone()
                if not video_data:
                    return False, f"Видео с ID {video_id} не найдено"
                
                user_id = video_data['user_id']
                
                
                detection_bucket_name = "logs" 
                
                
                cur.execute("""
                INSERT INTO detection_results 
                (video_id, user_id, s3_key, bucket_name, status, weapon_detected)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING result_id
                """, (video_id, user_id, log_filename, detection_bucket_name, 'completed', weapon_detected))
                
                result = cur.fetchone()
                
                cur.execute("""
                UPDATE videos 
                SET status = 'completed'
                WHERE video_id = %s
                """, (video_id,))
                
                conn.commit()
                logger.info(f"Сохранены результаты обнаружения для видео: {video_id}")
                return True, None
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при сохранении результатов обнаружения: {e}")
            return False, f"Ошибка при сохранении результатов обнаружения: {e}"
        finally:
            conn.close()
    
    def get_video_detections(self, video_id):
        """Получение результатов обнаружения для видео"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                SELECT dr.*, v.s3_key as video_s3_key, v.bucket_name as video_bucket_name
                FROM detection_results dr
                JOIN videos v ON dr.video_id = v.video_id
                WHERE dr.video_id = %s
                """, (video_id,))
                
                results = cur.fetchone()
                if not results:
                    return None
                
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении результатов обнаружения: {e}")
            return None
        finally:
            conn.close()
    
    def add_log(self, user_id, action, video_id=None, details=None):
        """
        Добавление записи в журнал действий
        
        :param user_id: ID пользователя
        :param action: Тип действия (строка)
        :param video_id: ID видео (опционально)
        :param details: Дополнительная информация в формате JSON (опционально)
        :return: True при успешном добавлении, False в случае ошибки
        """
        if details:
            if isinstance(details, dict):
                details = json.dumps(details)
            
            query = """
            INSERT INTO logs (user_id, action, video_id, details)
            VALUES (%s, %s, %s, %s)
            """
            params = (user_id, action, video_id, details)
        else:
            query = """
            INSERT INTO logs (user_id, action, video_id)
            VALUES (%s, %s, %s)
            """
            params = (user_id, action, video_id)
            
        _, error = self.execute_query(query, params, fetch=None)
        
        if error:
            logger.error(f"Ошибка добавления записи в журнал: {error}")
            return False
        
        logger.info(f"Добавлена запись в журнал: {action}")
        return True
    
    def get_user_logs(self, user_id, limit=100):
        """Получение журнала действий пользователя"""
        result, _ = self.execute_query(
            """
            SELECT l.*, v.s3_key
            FROM logs l
            LEFT JOIN videos v ON l.video_id = v.video_id
            WHERE l.user_id = %s
            ORDER BY l.timestamp DESC
            LIMIT %s
            """,
            (user_id, limit),
            fetch='all',
            cursor_factory=RealDictCursor
        )
        
        return result or []
