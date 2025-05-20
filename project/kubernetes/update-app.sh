#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Функция для проверки ошибок
handle_error() {
    echo -e "${RED}ОШИБКА: $1${NC}"
    exit 1
}

# Проверка наличия kubectl
if ! command -v kubectl &> /dev/null; then
    handle_error "kubectl не установлен"
fi

# Проверка подключения к кластеру
echo -e "${YELLOW}Проверка подключения к кластеру Kubernetes...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    handle_error "Нет подключения к кластеру Kubernetes"
fi

# Функция для создания или обновления деплоймента
create_or_update_deployment() {
    local deployment=$1
    local namespace=$2
    local image=$3
    local container_name=$4

    echo -e "${YELLOW}Проверка наличия $deployment...${NC}"
    
    # Проверяем, существует ли деплоймент
    if ! kubectl get deployment $deployment -n $namespace &> /dev/null; then
        echo -e "${YELLOW}Создание $deployment...${NC}"
        
        # Создаем деплоймент
        kubectl create deployment $deployment --image=$image -n $namespace || handle_error "Ошибка создания $deployment"
        
        # Создаем сервис
        if [ "$deployment" == "backend" ]; then
            kubectl expose deployment $deployment --port=5174 --target-port=5174 --type=NodePort -n $namespace || handle_error "Ошибка создания сервиса для $deployment"
        elif [ "$deployment" == "frontend" ]; then
            kubectl expose deployment $deployment --port=80 --target-port=80 --type=NodePort -n $namespace || handle_error "Ошибка создания сервиса для $deployment"
        fi
    else
        echo -e "${YELLOW}Обновление $deployment...${NC}"
        # Обновляем образ, используя правильное имя контейнера
        kubectl set image deployment/$deployment $container_name=$image -n $namespace || handle_error "Ошибка обновления $deployment"
    fi
    
    # Ждем завершения обновления
    echo -e "${YELLOW}Ожидание завершения обновления $deployment...${NC}"
    kubectl rollout status deployment/$deployment -n $namespace || handle_error "Ошибка при обновлении $deployment"
    
    echo -e "${GREEN}$deployment успешно обновлен!${NC}"
}

# Основные параметры
NAMESPACE="lab4-app"
DOCKER_USERNAME=${DOCKER_USERNAME:-"sngflu"}
VERSION=${VERSION:-"latest"}

# Обновление backend
create_or_update_deployment "backend" $NAMESPACE "$DOCKER_USERNAME/project-backend:$VERSION" "project-backend"

# Обновление frontend
create_or_update_deployment "frontend" $NAMESPACE "$DOCKER_USERNAME/project-frontend:$VERSION" "project-frontend"

echo -e "${GREEN}Приложение успешно обновлено!${NC}"
echo -e "${YELLOW}Проверка статуса подов:${NC}"
kubectl get pods -n $NAMESPACE 