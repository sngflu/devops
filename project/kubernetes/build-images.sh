#!/bin/bash
# Запуск sudo -E ./build-images.sh
# Установка переменных окружения
if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
  echo "PROJECT_DIR установлен как: $PROJECT_DIR"
fi

# Функция для обработки ошибок
handle_error() {
  echo "ОШИБКА: $1"
  exit 1
}

# Проверка версии Docker
docker --version || handle_error "Docker не установлен"

# Аккаунт Docker Hub
# Используем переменную окружения DOCKER_USERNAME если она задана, иначе используем значение по умолчанию
DOCKER_USERNAME=${DOCKER_USERNAME:-"sanchous1000"}
REGISTRY="$DOCKER_USERNAME"
# Создаем версию на основе даты или из переменной VERSION
VERSION=${VERSION:-$(date +"%Y.%m.%d-%H%M")}
echo "Используем Docker Hub аккаунт: $DOCKER_USERNAME"
echo "Версия образов: $VERSION"

# Проверка авторизации в Docker Hub
echo "Проверка авторизации в Docker Hub..."
# Проверяем, авторизован ли пользователь
if ! docker info | grep -q "Username: $DOCKER_USERNAME"; then
  # Проверка наличия переменных окружения для автоматической авторизации
  if [ -n "$DOCKER_HUB_PASSWORD" ]; then
    echo "Выполняется автоматическая авторизация для $DOCKER_USERNAME..."
    echo "$DOCKER_HUB_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin || handle_error "Ошибка автоматической авторизации"
  else
    # Интерактивная авторизация
    echo "Пожалуйста, введите учетные данные для $DOCKER_USERNAME"
    docker login -u "$DOCKER_USERNAME" || handle_error "Ошибка авторизации в Docker Hub"
  fi
fi

# Сборка и отправка в Docker Hub образа backend
echo "Сборка backend образа..."
echo "$PROJECT_DIR"
cd "$PROJECT_DIR/backend" || handle_error "Директория backend не найдена"
docker build -t "$REGISTRY/backend:$VERSION" -t "$REGISTRY/backend:latest" . || handle_error "Ошибка сборки backend образа"
docker push "$REGISTRY/backend:$VERSION" || handle_error "Ошибка отправки backend:$VERSION"
docker push "$REGISTRY/backend:latest" || handle_error "Ошибка отправки backend:latest"

# Сборка и отправка в Docker Hub образа frontend
echo "Сборка frontend образа..."
cd "$PROJECT_DIR/frontend" || handle_error "Директория frontend не найдена"
docker build -t "$REGISTRY/frontend:$VERSION" -t "$REGISTRY/frontend:latest" . || handle_error "Ошибка сборки frontend образа"
docker push "$REGISTRY/frontend:$VERSION" || handle_error "Ошибка отправки frontend:$VERSION"
docker push "$REGISTRY/frontend:latest" || handle_error "Ошибка отправки frontend:latest"

echo "Образы успешно собраны и отправлены в Docker Hub:"
echo "- $REGISTRY/backend:latest, версия: $VERSION"
echo "- $REGISTRY/frontend:latest, версия: $VERSION"

# Обновляем манифесты Kubernetes
echo "Обновление манифестов Kubernetes..."
cd "$PROJECT_DIR/kubernetes" || handle_error "Директория kubernetes не найдена"

# Обновляем ссылки на образы в файлах деплоймента
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS использует sed с другим синтаксисом
  sed -i '' "s|image: \${DOCKER_REGISTRY:-localhost}/backend:.*|image: $REGISTRY/backend:$VERSION|g" backend/deployment.yaml || handle_error "Ошибка обновления backend/deployment.yaml"
  sed -i '' "s|image: \${DOCKER_REGISTRY:-localhost}/frontend:.*|image: $REGISTRY/frontend:$VERSION|g" frontend/deployment.yaml || handle_error "Ошибка обновления frontend/deployment.yaml"
else
  # Linux
  sed -i "s|image: \${DOCKER_REGISTRY:-localhost}/backend:.*|image: $REGISTRY/backend:$VERSION|g" backend/deployment.yaml || handle_error "Ошибка обновления backend/deployment.yaml"
  sed -i "s|image: \${DOCKER_REGISTRY:-localhost}/frontend:.*|image: $REGISTRY/frontend:$VERSION|g" frontend/deployment.yaml || handle_error "Ошибка обновления frontend/deployment.yaml"
fi

echo "Манифесты обновлены."
echo "Теперь вы можете применить манифесты к кластеру Kubernetes с помощью команды:"
echo "kubectl apply -f kubernetes/namespace.yaml"
echo "kubectl apply -f kubernetes/" 