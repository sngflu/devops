#!/bin/bash

# Остановить скрипт при ошибке
set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Запуск приложения DevOps в Kubernetes...${NC}"

# Проверка работы minikube
if ! minikube status | grep -q "Running"; then
  echo -e "${YELLOW}Minikube не запущен. Запускаем...${NC}"
  minikube start --driver=docker --insecure-registry="host.minikube.internal:5000"
  echo -e "${GREEN}Minikube запущен успешно!${NC}"
else
  echo -e "${GREEN}Minikube уже запущен.${NC}"
fi

# Проверяем аддон ingress
if ! minikube addons list | grep -q "ingress.*enabled"; then
  echo -e "${YELLOW}Включаем аддон ingress...${NC}"
  minikube addons enable ingress
  echo -e "${GREEN}Аддон ingress включен!${NC}"
else
  echo -e "${GREEN}Аддон ingress уже включен.${NC}"
fi

# Настройка Docker для работы с Minikube
echo -e "${YELLOW}Настройка Docker для работы с Minikube...${NC}"
eval $(minikube docker-env)
echo -e "${GREEN}Docker настроен для работы с Minikube: DOCKER_HOST=$DOCKER_HOST${NC}"

# Проверяем наличие пространства имен
if ! kubectl get namespace app-namespace > /dev/null 2>&1; then
  echo -e "${YELLOW}Создаем пространство имен app-namespace...${NC}"
  kubectl apply -f namespace.yaml
  echo -e "${GREEN}Пространство имен создано!${NC}"
else
  echo -e "${GREEN}Пространство имен app-namespace уже существует.${NC}"
fi

# Запускаем компоненты приложения
echo -e "${YELLOW}Запускаем базу данных...${NC}"
kubectl apply -f postgres

echo -e "${YELLOW}Запускаем хранилище Minio...${NC}"
kubectl apply -f minio

echo -e "${YELLOW}Запускаем бэкенд...${NC}"
kubectl apply -f backend

echo -e "${YELLOW}Запускаем фронтенд...${NC}"
kubectl apply -f frontend

echo -e "${YELLOW}Настраиваем Ingress...${NC}"
kubectl apply -f ingress.yaml

# Ждем, пока все поды запустятся
echo -e "${YELLOW}Ожидаем запуска всех компонентов...${NC}"
kubectl wait --for=condition=Ready pods --all -n app-namespace --timeout=180s

echo -e "${GREEN}Все компоненты запущены успешно!${NC}"

# Запускаем port-forwarding в фоновом режиме
echo -e "${YELLOW}Запускаем port-forwarding для frontend на порт 4000...${NC}"
kubectl port-forward -n app-namespace svc/frontend 4000:80 > /dev/null 2>&1 &
FRONTEND_PID=$!

echo -e "${YELLOW}Запускаем port-forwarding для backend на порт 4001...${NC}"
kubectl port-forward -n app-namespace svc/backend 4001:5174 > /dev/null 2>&1 &
BACKEND_PID=$!

# Выводим информацию о доступе
echo -e "${GREEN}"
echo "========================================================================================="
echo "Приложение запущено и доступно по следующим адресам:"
echo "Frontend: http://localhost:4000"
echo "Backend API: http://localhost:4001"
echo "========================================================================================="
echo "Процессы port-forwarding запущены с PID: $FRONTEND_PID (frontend) и $BACKEND_PID (backend)"
echo "Для остановки port-forwarding используйте: kill $FRONTEND_PID $BACKEND_PID"
echo "========================================================================================="
echo -e "${NC}"

# Ожидаем завершения процессов port-forwarding
echo -e "${YELLOW}Port-forwarding работает. Нажмите Ctrl+C для завершения.${NC}"
wait $FRONTEND_PID $BACKEND_PID 