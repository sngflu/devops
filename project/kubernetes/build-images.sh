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

# Остановка и удаление существующего registry если он запущен
if docker ps -a | grep -q registry; then
  echo "Остановка и удаление существующего Docker Registry..."
  docker stop registry || true
  docker rm registry || true
fi

# Запуск локального Docker registry
echo "Запуск локального Docker Registry..."
docker run -d --name registry -p 5000:5000 --restart=always registry:2

# Даем время на запуск registry
sleep 3

# Репозиторий Docker Registry для локальной сборки
REGISTRY="localhost:5000"
echo "Используем registry по адресу: $REGISTRY"

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

# Обновляем манифесты Kubernetes, чтобы использовать образы из registry доступного из кластера
echo "Обновление манифестов Kubernetes..."
cd "$PROJECT_DIR/kubernetes"

# Адрес registry для доступа изнутри кластера Kubernetes
# У кластера должен быть доступ к хосту через специальный DNS-адрес
K8S_REGISTRY="host.minikube.internal:5000"
echo "Для кластера Kubernetes используем registry по адресу: $K8S_REGISTRY"

# Обновляем ссылки на образы в файлах деплоймента
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS использует sed с другим синтаксисом
  sed -i '' "s|image: localhost:5000/backend:latest|image: $K8S_REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i '' "s|image: localhost:5000/frontend:latest|image: $K8S_REGISTRY/frontend:latest|g" frontend/deployment.yaml
else
  # Linux
  sed -i "s|image: localhost:5000/backend:latest|image: $K8S_REGISTRY/backend:latest|g" backend/deployment.yaml
  sed -i "s|image: localhost:5000/frontend:latest|image: $K8S_REGISTRY/frontend:latest|g" frontend/deployment.yaml
fi

echo "Манифесты обновлены."
echo "Теперь вы можете применить манифесты к кластеру Kubernetes с помощью команды:"
echo "kubectl apply -f kubernetes/namespace.yaml"
echo "kubectl apply -f kubernetes/" 