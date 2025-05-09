#!/bin/bash

# Остановить скрипт при ошибке
set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Запуск мониторинга для приложения в Kubernetes...${NC}"

# Проверка работы minikube
if ! minikube status | grep -q "Running"; then
  echo -e "${YELLOW}Minikube не запущен. Запускаем...${NC}"
  minikube start --driver=docker
  echo -e "${GREEN}Minikube запущен успешно!${NC}"
else
  echo -e "${GREEN}Minikube уже запущен.${NC}"
fi

# Проверяем аддон metrics-server
if ! minikube addons list | grep -q "metrics-server.*enabled"; then
  echo -e "${YELLOW}Включаем аддон metrics-server...${NC}"
  minikube addons enable metrics-server
  echo -e "${GREEN}Аддон metrics-server включен!${NC}"
else
  echo -e "${GREEN}Аддон metrics-server уже включен.${NC}"
fi

# Проверяем наличие пространства имен
if ! kubectl get namespace app-namespace > /dev/null 2>&1; then
  echo -e "${YELLOW}Создаем пространство имен app-namespace...${NC}"
  kubectl apply -f namespace.yaml
  echo -e "${GREEN}Пространство имен создано!${NC}"
else
  echo -e "${GREEN}Пространство имен app-namespace уже существует.${NC}"
fi

# Запускаем компоненты мониторинга
echo -e "${YELLOW}Запускаем Prometheus...${NC}"
kubectl apply -f monitoring/prometheus/configmap.yaml -n app-namespace
kubectl apply -f monitoring/prometheus/deployment.yaml -n app-namespace
kubectl apply -f monitoring/prometheus/service.yaml -n app-namespace

echo -e "${YELLOW}Запускаем Grafana...${NC}"
kubectl apply -f monitoring/grafana/configmap.yaml -n app-namespace
kubectl apply -f monitoring/grafana/deployment.yaml -n app-namespace
kubectl apply -f monitoring/grafana/service.yaml -n app-namespace

# Ждем, пока все поды запустятся
echo -e "${YELLOW}Ожидаем запуска всех компонентов мониторинга...${NC}"
kubectl wait --for=condition=Ready pods -l app=prometheus -n app-namespace --timeout=120s
kubectl wait --for=condition=Ready pods -l app=grafana -n app-namespace --timeout=120s

echo -e "${GREEN}Все компоненты мониторинга запущены успешно!${NC}"

# Запускаем port-forwarding в фоновом режиме
echo -e "${YELLOW}Запускаем port-forwarding для Prometheus на порт 9090...${NC}"
kubectl port-forward -n app-namespace svc/prometheus 9090:9090 > /dev/null 2>&1 &
PROMETHEUS_PID=$!

echo -e "${YELLOW}Запускаем port-forwarding для Grafana на порт 3000...${NC}"
kubectl port-forward -n app-namespace svc/grafana 3000:3000 > /dev/null 2>&1 &
GRAFANA_PID=$!

# Выводим информацию о доступе
echo -e "${GREEN}"
echo "========================================================================================="
echo "Мониторинг доступен по следующим адресам:"
echo "Prometheus: http://localhost:9090"
echo "Grafana: http://localhost:3000 (логин: admin, пароль: admin)"
echo "========================================================================================="
echo "Процессы port-forwarding запущены с PID:"
echo "- Prometheus: $PROMETHEUS_PID" 
echo "- Grafana: $GRAFANA_PID"
echo "Для остановки port-forwarding используйте: kill $PROMETHEUS_PID $GRAFANA_PID"
echo "========================================================================================="
echo -e "${NC}"

# Ожидаем завершения процессов port-forwarding
echo -e "${YELLOW}Port-forwarding работает. Нажмите Ctrl+C для завершения.${NC}"
wait $PROMETHEUS_PID $GRAFANA_PID 