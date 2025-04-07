-- Создание расширения для использования UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица пользователей
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    -- email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin'))
);

-- Таблица видео (обновлена для MinIO)
CREATE TABLE videos (
    video_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    s3_key VARCHAR(255) NOT NULL,
    bucket_name VARCHAR(100) NOT NULL,
    upload_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    metadata JSONB,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- Таблица результатов детекции
CREATE TABLE detection_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL UNIQUE,
    processed_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    weapon_detected BOOLEAN NOT NULL DEFAULT FALSE,
    summary JSONB,
    FOREIGN KEY (video_id) REFERENCES videos (video_id) ON DELETE CASCADE
);

-- Таблица отдельных обнаружений
CREATE TABLE detections (
    detection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    result_id UUID NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    weapon_type VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    FOREIGN KEY (result_id) REFERENCES detection_results (result_id) ON DELETE CASCADE
);

-- Таблица логов действий
CREATE TABLE logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    video_id UUID,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos (video_id) ON DELETE SET NULL
);

-- Индексы для улучшения производительности
CREATE INDEX idx_videos_user_id ON videos (user_id);
CREATE INDEX idx_detection_results_video_id ON detection_results (video_id);
CREATE INDEX idx_detections_result_id ON detections (result_id);
CREATE INDEX idx_logs_user_id ON logs (user_id);
CREATE INDEX idx_logs_video_id ON logs (video_id);
CREATE INDEX idx_videos_s3_key ON videos (s3_key);
CREATE INDEX idx_videos_bucket_name ON videos (bucket_name);

-- Добавляем тестового пользователя (admin/admin123)
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@example.com', '$2a$10$dbc.LGFN1qpH/VH2CeF4O.Hp.0CkE9rU8zrmGI1Rx2GYtye9ZNpLG', 'admin');

-- Добавляем обычного пользователя (user/user123)
INSERT INTO users (username, email, password_hash, role)
VALUES ('user', 'user@example.com', '$2a$10$Cy7FS7Z8CSKs0gWEkY4MuO0LDl.NlL3AYqEHtFhRzQCJXwqXRp9xK', 'user');

-- Добавляем пример видео в MinIO
INSERT INTO videos (user_id, s3_key, bucket_name, status, metadata)
VALUES 
((SELECT user_id FROM users WHERE username = 'admin'), 
 'videos/2025/04/06/sample1.mp4', 
 'weapon-detection', 
 'completed',
 '{"title": "Тестовое видео 1", "description": "Пример видео для тестирования системы", "duration": 120}'
); 