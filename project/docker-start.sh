#!/bin/bash

set -e

function start_containers() {
    echo "🚀 Запускаем контейнеры..."
    docker compose up -d
    
    echo "✅ Проект запущен!"
    echo "🌐 Фронтенд доступен по адресу: http://localhost:5173"
    echo "🔧 Бэкенд доступен по адресу: http://localhost:5174"
    echo "📊 PgAdmin доступен по адресу: http://localhost:5050"
    echo "💾 MinIO консоль доступна по адресу: http://localhost:9001"
    echo "⚠️ Для остановки проекта выполните: ./docker-start.sh stop"
}

function stop_containers() {
    echo "🛑 Останавливаем контейнеры..."
    docker compose down
    echo "✅ Проект остановлен!"
}

function build_containers() {
    echo "🔨 Собираем контейнеры..."
    docker compose build
    echo "✅ Сборка контейнеров завершена!"
}

case "$1" in
    "stop")
        stop_containers
        ;;
    "start")
        start_containers
        ;;
    "build")
        build_containers
        ;;
    "restart")
        stop_containers
        start_containers
        ;;
    *)
        build_containers
        start_containers
        ;;
esac 