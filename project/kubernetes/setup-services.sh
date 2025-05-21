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

# Функция для ожидания завершения подов
wait_for_pods_deletion() {
    local namespace=$1
    local timeout=60
    local interval=5
    
    echo -e "${YELLOW}Ожидание завершения подов в namespace $namespace...${NC}"
    for ((i=0; i<timeout; i+=interval)); do
        if ! kubectl get pods -n $namespace 2>/dev/null | grep -q .; then
            echo -e "${GREEN}Все поды завершены${NC}"
            return 0
        fi
        echo -e "${YELLOW}Ожидание завершения подов... (${i}s)${NC}"
        sleep $interval
    done
    handle_error "Таймаут ожидания завершения подов"
}

# Проверка наличия kubectl
if ! command -v kubectl &> /dev/null; then
    handle_error "kubectl не установлен"
fi

# Проверка подключения к кластеру
echo -e "${YELLOW}Проверка подключения к кластеру Kubernetes...${NC}"
run_with_timeout 30 "kubectl cluster-info" "Проверка подключения к кластеру"

# Функция для применения манифестов
apply_manifests() {
    local dir=$1
    local namespace=$2
    
    echo -e "${YELLOW}Применение манифестов из $dir...${NC}"
    
    # Применяем все yaml файлы в директории
    for file in $(find $dir -name "*.yaml" | sort); do
        echo -e "${YELLOW}Применение $file...${NC}"
        run_with_timeout 30 "kubectl apply -f $file -n $namespace" "Применение манифеста $file"
    done
}

# Функция для ожидания создания PV
wait_for_pv() {
    local pv_name=$1
    local timeout=60
    local interval=5
    
    echo -e "${YELLOW}Ожидание создания PV $pv_name...${NC}"
    for ((i=0; i<timeout; i+=interval)); do
        if kubectl get pv $pv_name &> /dev/null; then
            echo -e "${GREEN}PV $pv_name создан${NC}"
            return 0
        fi
        echo -e "${YELLOW}Ожидание создания PV $pv_name... (${i}s)${NC}"
        sleep $interval
    done
    handle_error "Таймаут ожидания создания PV $pv_name"
}

# Основные параметры
NAMESPACE="lab4-app"

# Удаляем все деплойменты в namespace
echo -e "${YELLOW}Удаление всех деплойментов в namespace $NAMESPACE...${NC}"
run_with_timeout 30 "kubectl delete deployment --all -n $NAMESPACE --force --grace-period=0" "Удаление деплойментов"

# Удаляем все поды в namespace
echo -e "${YELLOW}Удаление всех подов в namespace $NAMESPACE...${NC}"
run_with_timeout 30 "kubectl delete pods --all -n $NAMESPACE --force --grace-period=0" "Удаление подов"

# Ждем завершения подов
wait_for_pods_deletion $NAMESPACE

# Удаляем существующие PVC
echo -e "${YELLOW}Удаление существующих PVC...${NC}"
run_with_timeout 30 "kubectl delete pvc -n $NAMESPACE --all --force --grace-period=0" "Удаление PVC"

# Создаем PersistentVolume для Minio
echo -e "${YELLOW}Создание PersistentVolume для Minio...${NC}"
run_with_timeout 30 "kubectl apply -f minio/pv.yaml" "Создание PV для Minio"
wait_for_pv "minio-pv-lab4"

# Создаем PersistentVolume для Postgres
echo -e "${YELLOW}Создание PersistentVolume для Postgres...${NC}"
run_with_timeout 30 "kubectl apply -f postgres/pv.yaml" "Создание PV для Postgres"
wait_for_pv "postgres-pv-lab4"

# Создаем PersistentVolume для Prometheus
echo -e "${YELLOW}Создание PersistentVolume для Prometheus...${NC}"
run_with_timeout 30 "kubectl apply -f monitoring/prometheus/pv.yaml" "Создание PV для Prometheus"
wait_for_pv "prometheus-pv-lab4"

# Создаем PersistentVolume для Grafana
echo -e "${YELLOW}Создание PersistentVolume для Grafana...${NC}"
run_with_timeout 30 "kubectl apply -f monitoring/grafana/pv.yaml" "Создание PV для Grafana"
wait_for_pv "grafana-pv-lab4"

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
run_with_timeout 30 "kubectl get pods -n $NAMESPACE" "Проверка статуса подов" 