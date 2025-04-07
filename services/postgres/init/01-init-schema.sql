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

-- Таблица результатов детекции (обновлена для MinIO)
CREATE TABLE detection_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    s3_key VARCHAR(255) NOT NULL,
    bucket_name VARCHAR(100) NOT NULL,
    processed_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    weapon_detected BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (video_id) REFERENCES videos (video_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);



-- Таблица логов действий
CREATE TABLE logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    video_id UUID,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos (video_id) ON DELETE SET NULL
);

-- Индексы для улучшения производительности
CREATE INDEX idx_videos_user_id ON videos (user_id);
CREATE INDEX idx_detection_results_video_id ON detection_results (video_id);
CREATE INDEX idx_detection_results_user_id ON detection_results (user_id);
CREATE INDEX idx_detection_results_s3_key ON detection_results (s3_key);
CREATE INDEX idx_detection_results_bucket_name ON detection_results (bucket_name);
CREATE INDEX idx_logs_user_id ON logs (user_id);
CREATE INDEX idx_logs_video_id ON logs (video_id);
CREATE INDEX idx_videos_s3_key ON videos (s3_key);
CREATE INDEX idx_videos_bucket_name ON videos (bucket_name);

-- Добавляем тестового пользователя (admin/admin123)
INSERT INTO users (username, password_hash, role)
VALUES ('admin', '$2a$10$dbc.LGFN1qpH/VH2CeF4O.Hp.0CkE9rU8zrmGI1Rx2GYtye9ZNpLG', 'admin');

-- Добавляем обычного пользователя (user/user123)
INSERT INTO users (username, password_hash, role)
VALUES ('user', '$2a$10$Cy7FS7Z8CSKs0gWEkY4MuO0LDl.NlL3AYqEHtFhRzQCJXwqXRp9xK', 'user');

