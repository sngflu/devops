import os
import json
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid

# Регистрация UUID типа данных
register_uuid()

# Загрузка конфигурации базы данных
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'weapon_detection'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432')
}

def get_connection():
    """Получение соединения с базой данных"""
    try:
        conn = psycopg2.connect(
            dbname=DB_CONFIG['dbname'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

def init_database():
    """Инициализация базы данных при первом запуске"""
    conn = get_connection()
    if not conn:
        print("Не удалось подключиться к базе данных")
        return False
    
    try:
        with conn.cursor() as cur:
            # Создание таблиц, если они не существуют
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                role VARCHAR(10) NOT NULL DEFAULT 'user'
            );
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                upload_time TIMESTAMP NOT NULL DEFAULT NOW(),
                status VARCHAR(20) NOT NULL DEFAULT 'processed',
                metadata JSONB DEFAULT '{}'::jsonb,
                UNIQUE(filename)
            );
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS detection_results (
                result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                video_id UUID NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
                processed_time TIMESTAMP NOT NULL DEFAULT NOW(),
                weapon_detected BOOLEAN NOT NULL DEFAULT FALSE,
                summary JSONB DEFAULT '{}'::jsonb
            );
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                detection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                result_id UUID NOT NULL REFERENCES detection_results(result_id) ON DELETE CASCADE,
                frame_number INTEGER NOT NULL,
                timestamp VARCHAR(20),
                weapon_type VARCHAR(50),
                confidence FLOAT
            );
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
                action VARCHAR(50) NOT NULL,
                video_id UUID REFERENCES videos(video_id) ON DELETE SET NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)
            
            conn.commit()
            print("База данных успешно инициализирована")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"Ошибка инициализации базы данных: {e}")
        return False
    finally:
        conn.close()

# Функции для работы с пользователями
def create_user(username, password_hash, email=None, role='user'):
    """Создание нового пользователя"""
    conn = get_connection()
    if not conn:
        return None, "Ошибка подключения к БД"
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO users (username, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
            """, (username, email, password_hash, role))
            
            result = cur.fetchone()
            conn.commit()
            return result['user_id'], None
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return None, "Пользователь с таким именем или email уже существует"
    except Exception as e:
        conn.rollback()
        return None, f"Ошибка при создании пользователя: {e}"
    finally:
        conn.close()

def get_user_by_username(username):
    """Получение пользователя по имени пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
            SELECT * FROM users WHERE username = %s
            """, (username,))
            
            return cur.fetchone()
    except Exception as e:
        print(f"Ошибка при получении пользователя: {e}")
        return None
    finally:
        conn.close()

# Функции для работы с видео
def save_video_metadata(user_id, filename, metadata=None):
    """Сохранение метаданных видео"""
    conn = get_connection()
    if not conn:
        return None, "Ошибка подключения к БД"
    
    if metadata is None:
        metadata = {}
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
            INSERT INTO videos (user_id, filename, metadata)
            VALUES (%s, %s, %s)
            RETURNING video_id
            """, (user_id, filename, json.dumps(metadata)))
            
            result = cur.fetchone()
            conn.commit()
            return result['video_id'], None
    except Exception as e:
        conn.rollback()
        return None, f"Ошибка при сохранении видео: {e}"
    finally:
        conn.close()

def get_user_videos(user_id):
    """Получение видео пользователя"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
            SELECT v.*, 
                   CASE WHEN dr.weapon_detected THEN true ELSE false END as weapon_detected,
                   dr.result_id
            FROM videos v
            LEFT JOIN detection_results dr ON v.video_id = dr.video_id
            WHERE v.user_id = %s
            ORDER BY v.upload_time DESC
            """, (user_id,))
            
            return cur.fetchall()
    except Exception as e:
        print(f"Ошибка при получении видео: {e}")
        return []
    finally:
        conn.close()

def delete_video(video_id, user_id):
    """Удаление видео"""
    conn = get_connection()
    if not conn:
        return False, "Ошибка подключения к БД"
    
    try:
        with conn.cursor() as cur:
            # Проверка принадлежности видео пользователю
            cur.execute("""
            SELECT filename FROM videos 
            WHERE video_id = %s AND user_id = %s
            """, (video_id, user_id))
            
            video = cur.fetchone()
            if not video:
                return False, "Видео не найдено или нет доступа"
            
            # Удаление видео
            cur.execute("""
            DELETE FROM videos 
            WHERE video_id = %s
            """, (video_id,))
            
            # Логирование действия
            cur.execute("""
            INSERT INTO logs (user_id, action, video_id)
            VALUES (%s, %s, %s)
            """, (user_id, 'delete', video_id))
            
            conn.commit()
            return True, video[0]  # Возвращаем имя файла
    except Exception as e:
        conn.rollback()
        return False, f"Ошибка при удалении видео: {e}"
    finally:
        conn.close()

# Функции для работы с результатами обнаружения
def save_detection_results(video_id, frame_objects, fps):
    """Сохранение результатов обнаружения"""
    conn = get_connection()
    if not conn:
        return None, "Ошибка подключения к БД"
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Определение, было ли обнаружено оружие
            weapon_detected = any(fo[1] > 0 or fo[2] > 0 for fo in frame_objects)
            
            # Создание сводки
            total_weapons = sum(fo[1] for fo in frame_objects)
            total_knives = sum(fo[2] for fo in frame_objects)
            frames_with_weapons = sum(1 for fo in frame_objects if fo[1] > 0)
            frames_with_knives = sum(1 for fo in frame_objects if fo[2] > 0)
            
            summary = {
                'total_frames': len(frame_objects),
                'total_weapons': total_weapons,
                'total_knives': total_knives,
                'frames_with_weapons': frames_with_weapons,
                'frames_with_knives': frames_with_knives,
                'fps': fps
            }
            
            # Сохранение результата
            cur.execute("""
            INSERT INTO detection_results (video_id, weapon_detected, summary)
            VALUES (%s, %s, %s)
            RETURNING result_id
            """, (video_id, weapon_detected, json.dumps(summary)))
            
            result = cur.fetchone()
            result_id = result['result_id']
            
            # Сохранение отдельных обнаружений
            for fo in frame_objects:
                frame_number, num_weapons, num_knives = fo
                
                if num_weapons > 0:
                    cur.execute("""
                    INSERT INTO detections (result_id, frame_number, timestamp, weapon_type, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (result_id, frame_number, str(frame_number / fps), 'weapon', 1.0))
                
                if num_knives > 0:
                    cur.execute("""
                    INSERT INTO detections (result_id, frame_number, timestamp, weapon_type, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (result_id, frame_number, str(frame_number / fps), 'knife', 1.0))
            
            conn.commit()
            return result_id, None
    except Exception as e:
        conn.rollback()
        return None, f"Ошибка при сохранении результатов: {e}"
    finally:
        conn.close()

def get_video_detections(video_id):
    """Получение результатов обнаружения для видео"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Получение сводки результатов
            cur.execute("""
            SELECT * FROM detection_results
            WHERE video_id = %s
            """, (video_id,))
            
            result = cur.fetchone()
            if not result:
                return None
            
            # Получение детальных результатов
            cur.execute("""
            SELECT * FROM detections
            WHERE result_id = %s
            ORDER BY frame_number
            """, (result['result_id'],))
            
            detections = cur.fetchall()
            
            # Объединение результатов
            result['detections'] = detections
            return result
    except Exception as e:
        print(f"Ошибка при получении результатов обнаружения: {e}")
        return None
    finally:
        conn.close()

# Функции для работы с логами
def add_log(user_id, action, video_id=None):
    """Добавление записи в лог"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO logs (user_id, action, video_id)
            VALUES (%s, %s, %s)
            """, (user_id, action, video_id))
            
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при добавлении лога: {e}")
        return False
    finally:
        conn.close()

def get_user_logs(user_id, limit=100):
    """Получение логов пользователя"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
            SELECT l.*, v.filename
            FROM logs l
            LEFT JOIN videos v ON l.video_id = v.video_id
            WHERE l.user_id = %s
            ORDER BY l.timestamp DESC
            LIMIT %s
            """, (user_id, limit))
            
            return cur.fetchall()
    except Exception as e:
        print(f"Ошибка при получении логов: {e}")
        return []
    finally:
        conn.close() 