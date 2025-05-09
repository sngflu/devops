#!/bin/bash

# Остановить скрипт при ошибке
set -e

# Переходим в директорию проекта
cd "$(dirname "$0")"

echo "Проверка доступности кластера Kubernetes (Minikube)..."
if ! minikube status &>/dev/null; then
    echo "Minikube не запущен. Запускаем..."
    minikube start --driver=docker --cpus=4 --memory=4096 --disk-size=20g
fi

echo "Включение необходимых дополнений Minikube..."
minikube addons enable ingress
minikube addons enable metrics-server

echo "Создание namespace..."
kubectl apply -f namespace.yaml

echo "Деплой PostgreSQL..."
kubectl apply -f postgres/

echo "Деплой MinIO..."
kubectl apply -f minio/

echo "Ожидание запуска базовых сервисов..."
kubectl wait --for=condition=available --timeout=300s deployment/postgres -n app-namespace
kubectl wait --for=condition=available --timeout=300s deployment/minio -n app-namespace

echo "Деплой бэкенда..."
kubectl apply -f backend/

echo "Деплой фронтенда..."
kubectl apply -f frontend/

echo "Деплой мониторинга (Prometheus, Grafana)..."
kubectl apply -f monitoring/

echo "Настройка Ingress..."
kubectl apply -f ingress.yaml

echo "Проверка статуса подов..."
kubectl get pods -n app-namespace

echo "Проверка статуса сервисов..."
kubectl get svc -n app-namespace

echo "Проверка статуса ingress..."
kubectl get ingress -n app-namespace

echo "==============================================="
echo "Приложение развернуто в кластере Kubernetes!"
echo "==============================================="
echo "Убедитесь, что в вашем файле /etc/hosts добавлена строка:"
echo "127.0.0.1 app.local"
echo ""
echo "Чтобы получить доступ к приложению, запустите в отдельном терминале:"
echo "minikube tunnel"
echo ""
echo "Доступы к приложению:"
echo "- Фронтенд: http://app.local"
echo "- Бэкенд API: http://app.local/api"
echo "- Prometheus: http://app.local/prometheus"
echo "- Grafana: http://app.local/grafana"
echo "- MinIO консоль: http://app.local/minio"
echo ""
echo "Для отслеживания автомасштабирования бэкенда используйте команду:"
echo "kubectl get hpa -n app-namespace -w" 