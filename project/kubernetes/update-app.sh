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

# Функция для выполнения команд с таймаутом
run_with_timeout() {
    local timeout=$1
    local command=$2
    local description=$3
    
    echo -e "${YELLOW}Выполнение: $description${NC}"
    timeout $timeout bash -c "$command" || handle_error "Таймаут выполнения: $description"
}

# Проверка наличия kubectl
if ! command -v kubectl &> /dev/null; then
    handle_error "kubectl не установлен"
fi

# Проверка подключения к кластеру
echo -e "${YELLOW}Проверка подключения к кластеру Kubernetes...${NC}"
run_with_timeout 30 "kubectl cluster-info" "Проверка подключения к кластеру"

# Функция для обновления приложения
update_app() {
    local app_name=$1
    local namespace="lab4-app"
    local manifest_dir="/home/terra/kubernetes/$app_name"
    
    echo -e "${YELLOW}Проверка наличия $app_name...${NC}"
    if kubectl get deployment $app_name -n $namespace &> /dev/null; then
        echo -e "${YELLOW}Обновление $app_name...${NC}"
        # Удаляем существующий сервис
        kubectl delete service $app_name -n $namespace --force --grace-period=0 2>/dev/null || true
        # Обновляем деплоймент
        kubectl set image deployment/$app_name $app_name=sngflu/project-$app_name:latest -n $namespace || handle_error "Не удалось обновить образ $app_name"
        echo -e "${YELLOW}Ожидание завершения обновления $app_name...${NC}"
        kubectl rollout status deployment/$app_name -n $namespace --timeout=90s || handle_error "Таймаут обновления $app_name"
        
        # Проверяем, что поды запустились
        echo -e "${YELLOW}Проверка готовности подов $app_name...${NC}"
        kubectl wait --for=condition=ready pod -l app=$app_name -n $namespace --timeout=90s || handle_error "Поды $app_name не запустились"
        
        echo -e "${GREEN}$app_name успешно обновлен!${NC}"
    else
        echo -e "${YELLOW}Создание $app_name...${NC}"
        # Удаляем существующий сервис если он есть
        kubectl delete service $app_name -n $namespace --force --grace-period=0 2>/dev/null || true
        # Создаем деплоймент
        kubectl apply -f $manifest_dir/deployment.yaml || handle_error "Не удалось создать деплоймент $app_name"
        # Создаем сервис
        kubectl apply -f $manifest_dir/service.yaml || handle_error "Не удалось создать сервис $app_name"
        
        # Ждем запуска подов
        echo -e "${YELLOW}Ожидание запуска подов $app_name...${NC}"
        kubectl wait --for=condition=ready pod -l app=$app_name -n $namespace --timeout=90s || handle_error "Поды $app_name не запустились"
        
        echo -e "${GREEN}$app_name успешно создан!${NC}"
    fi
}

# Обновляем backend
update_app "backend"

# Обновляем frontend
update_app "frontend"

# Проверяем, что все поды работают
echo -e "${YELLOW}Проверка статуса всех подов...${NC}"
kubectl get pods -n lab4-app

echo -e "${GREEN}Все приложения успешно обновлены!${NC}" 