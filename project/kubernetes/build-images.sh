#!/bin/bash

# Остановить скрипт при ошибке
set -e

# Настройка Docker для работы с Minikube
echo "Настройка Docker для работы с Minikube..."
eval $(minikube docker-env)
echo "Docker настроен для работы с Minikube: DOCKER_HOST=$DOCKER_HOST"

# Переходим в директорию проекта
cd "$(dirname "$0")/.."

# Текущая директория
PROJECT_DIR=$(pwd)
echo "Директория проекта: $PROJECT_DIR"

# Хост и порт minikube
MINIKUBE_IP=$(minikube ip)
echo "IP Minikube: $MINIKUBE_IP"

# Проверка версии Docker
docker --version

# Аккаунт Docker Hub
DOCKER_USERNAME="sanchous1000"
REGISTRY="$DOCKER_USERNAME"
echo "Используем Docker Hub аккаунт: $DOCKER_USERNAME"

# Проверка авторизации в Docker Hub
echo "Проверка авторизации в Docker Hub..."
docker login

# Сборка и отправка в Docker Hub образа backend
echo "Сборка backend образа..."
cd "$PROJECT_DIR/backend"
docker build -t "$REGISTRY/backend:latest" .
docker push "$REGISTRY/backend:latest"

# Сборка и отправка в Docker Hub образа frontend
echo "Сборка frontend образа..."
cd "$PROJECT_DIR/frontend"
docker build -t "$REGISTRY/frontend:latest" .
docker push "$REGISTRY/frontend:latest"

echo "Образы успешно собраны и отправлены в Docker Hub:"
echo "- $REGISTRY/backend:latest"
echo "- $REGISTRY/frontend:latest"

# Обновляем манифесты Kubernetes
echo "Обновление манифестов Kubernetes..."
cd "$PROJECT_DIR/kubernetes"

# Обновляем ссылки на образы в файлах деплоймента
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS использует sed с другим синтаксисом
  sed -i '' "s|image: localhost:5000/backend:latest|image: $REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i '' "s|image: localhost:5000/frontend:latest|image: $REGISTRY/frontend:latest|g" frontend/deployment.yaml
else
  # Linux
  sed -i "s|image: localhost:5000/backend:latest|image: $REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i "s|image: localhost:5000/frontend:latest|image: $REGISTRY/frontend:latest|g" frontend/deployment.yaml
fi

echo "Манифесты обновлены."
echo "Теперь вы можете применить манифесты к кластеру Kubernetes с помощью команды:"
echo "kubectl apply -f kubernetes/namespace.yaml"
echo "kubectl apply -f kubernetes/" 