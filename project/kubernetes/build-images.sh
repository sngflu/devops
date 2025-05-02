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

# Репозиторий Docker Registry
REGISTRY="localhost:5000"

# Проверка версии Docker
docker --version

# Запуск локального Docker registry, если он ещё не запущен
if ! docker ps | grep -q registry; then
  echo "Запуск локального Docker Registry..."
  docker run -d -p 5000:5000 --restart=always --name registry registry:2
else
  echo "Локальный Docker Registry уже запущен"
fi

# Сборка и отправка в registry образа backend
echo "Сборка backend образа..."
cd "$PROJECT_DIR/backend"
docker build -t "$REGISTRY/backend:latest" .
docker push "$REGISTRY/backend:latest"

# Сборка и отправка в registry образа frontend
echo "Сборка frontend образа..."
cd "$PROJECT_DIR/frontend"
docker build -t "$REGISTRY/frontend:latest" .
docker push "$REGISTRY/frontend:latest"

echo "Образы успешно собраны и отправлены в registry:"
echo "- $REGISTRY/backend:latest"
echo "- $REGISTRY/frontend:latest"

# Обновляем манифесты Kubernetes, чтобы использовать образы из registry
echo "Обновление манифестов Kubernetes..."
cd "$PROJECT_DIR/kubernetes"

# Обновляем ссылки на образы в файлах деплоймента
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS использует sed с другим синтаксисом
  sed -i '' "s|image: backend:latest|image: $REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i '' "s|image: frontend:latest|image: $REGISTRY/frontend:latest|g" frontend/deployment.yaml
else
  # Linux
  sed -i "s|image: backend:latest|image: $REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i "s|image: frontend:latest|image: $REGISTRY/frontend:latest|g" frontend/deployment.yaml
fi

echo "Манифесты обновлены."
echo "Теперь вы можете применить манифесты к кластеру Kubernetes с помощью команды:"
echo "kubectl apply -f kubernetes/namespace.yaml"
echo "kubectl apply -f kubernetes/" 