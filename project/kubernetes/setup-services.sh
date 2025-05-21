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

# Функция для применения манифестов
apply_manifests() {
    local dir=$1
    local namespace=$2
    
    echo -e "${YELLOW}Применение манифестов из $dir...${NC}"
    
    # Применяем все yaml файлы в директории
    for file in $(find $dir -name "*.yaml" | sort); do
        echo -e "${YELLOW}Применение $file...${NC}"
        kubectl apply -f $file -n $namespace || handle_error "Ошибка применения $file"
    done
}

# Основные параметры
NAMESPACE="lab4-app"

# Удаляем существующие PVC
echo -e "${YELLOW}Удаление существующих PVC...${NC}"
kubectl delete pvc -n $NAMESPACE --all --force --grace-period=0

# Создаем PersistentVolume для Minio
echo -e "${YELLOW}Создание PersistentVolume для Minio...${NC}"
kubectl apply -f minio/pv.yaml || handle_error "Ошибка создания PV для Minio"

# Создаем PersistentVolume для Postgres
echo -e "${YELLOW}Создание PersistentVolume для Postgres...${NC}"
kubectl apply -f postgres/pv.yaml || handle_error "Ошибка создания PV для Postgres"

# Создаем PersistentVolume для Prometheus
echo -e "${YELLOW}Создание PersistentVolume для Prometheus...${NC}"
kubectl apply -f monitoring/prometheus/pv.yaml || handle_error "Ошибка создания PV для Prometheus"

# Создаем PersistentVolume для Grafana
echo -e "${YELLOW}Создание PersistentVolume для Grafana...${NC}"
kubectl apply -f monitoring/grafana/pv.yaml || handle_error "Ошибка создания PV для Grafana"

# Разворачиваем Minio
echo -e "${YELLOW}Развертывание Minio...${NC}"
apply_manifests "minio" $NAMESPACE

# Разворачиваем Postgres
echo -e "${YELLOW}Развертывание Postgres...${NC}"
apply_manifests "postgres" $NAMESPACE

# Разворачиваем Prometheus
echo -e "${YELLOW}Развертывание Prometheus...${NC}"
apply_manifests "monitoring/prometheus" $NAMESPACE

# Разворачиваем Grafana
echo -e "${YELLOW}Развертывание Grafana...${NC}"
apply_manifests "monitoring/grafana" $NAMESPACE

echo -e "${GREEN}Все сервисы успешно развернуты!${NC}"
echo -e "${YELLOW}Проверка статуса подов:${NC}"
kubectl get pods -n $NAMESPACE 