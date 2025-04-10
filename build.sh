#!/bin/bash

set -e  # Прервать выполнение скрипта при ошибке

function build_frontend() {
    echo "🌐 Начинаем сборку frontend..."
    # Установка зависимостей для frontend
    echo "📦 Установка зависимостей frontend..."
    cd frontend
    npm install
    cd ..
    echo "✅ Сборка frontend успешно завершена!"
}

function build_backend() {
    echo "🔧 Начинаем сборку backend..."
    # Установка зависимостей для backend
    echo "📦 Установка зависимостей backend..."
    cd backend
    python -m pip install -r requirements.txt
    cd ..
    echo "✅ Сборка backend успешно завершена!"
}

function build_project() {
    echo "🚀 Начинаем сборку всего проекта..."

    build_frontend
    build_backend

    echo "✅ Сборка проекта успешно завершена!"
}

function start_project() {
    echo "🚀 Запускаем проект..."
    
    # Запуск бэкенда
    echo "🔧 Запуск backend..."
    cd backend
    python wsgi.py > ../backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid
    cd ..
    
    # Запуск фронтенда
    echo "🌐 Запуск frontend..."
    cd frontend
    npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    cd ..
    
    echo "✅ Проект запущен!"
    echo "🌐 Фронтенд доступен по адресу: http://localhost:5173/login"
    echo "📝 Логи бэкенда: backend.log"
    echo "📝 Логи фронтенда: frontend.log"
    echo "⚠️ Для остановки проекта выполните: ./build.sh stop"
}

function stop_project() {
    echo "🛑 Останавливаем проект..."
    
    # Остановка бэкенда
    if [ -f "backend.pid" ]; then
        BACKEND_PID=$(cat backend.pid)
        if ps -p $BACKEND_PID > /dev/null; then
            echo "🔧 Останавливаем backend (PID: $BACKEND_PID)..."
            kill $BACKEND_PID
        else
            echo "🔧 Процесс backend (PID: $BACKEND_PID) уже остановлен"
        fi
        rm backend.pid
    else
        echo "🔧 Файл с PID для backend не найден"
        pkill -f "python wsgi.py" || true
    fi
    
    # Остановка фронтенда
    if [ -f "frontend.pid" ]; then
        FRONTEND_PID=$(cat frontend.pid)
        if ps -p $FRONTEND_PID > /dev/null; then
            echo "🌐 Останавливаем frontend (PID: $FRONTEND_PID)..."
            kill $FRONTEND_PID
        else
            echo "🌐 Процесс frontend (PID: $FRONTEND_PID) уже остановлен"
        fi
        rm frontend.pid
    else
        echo "🌐 Файл с PID для frontend не найден"
        pkill -f "node.*vite" || true
    fi
    
    echo "✅ Проект остановлен!"
}

case "$1" in
    "stop")
        stop_project
        ;;
    "start")
        start_project
        ;;
    "build")
        build_project
        ;;
    "build-frontend")
        build_frontend
        ;;
    "build-backend")
        build_backend
        ;;
    *)
        build_project
        start_project
        ;;
esac 