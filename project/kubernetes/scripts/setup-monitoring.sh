#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Настройка мониторинга в Kubernetes...${NC}"

# Проверяем подключение к Kubernetes
kubectl cluster-info > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo -e "${RED}Ошибка: Нет подключения к Kubernetes!${NC}"
  exit 1
fi

# Создаем namespace, если он еще не существует
if ! kubectl get ns app-namespace > /dev/null 2>&1; then
  echo -e "${YELLOW}Создаем namespace app-namespace...${NC}"
  kubectl apply -f /home/terra/devops/project/kubernetes/namespace.yaml
  echo -e "${GREEN}Namespace создан!${NC}"
fi

# Проверяем наличие metrics-server
if ! kubectl get deployment metrics-server -n kube-system > /dev/null 2>&1; then
  echo -e "${YELLOW}Устанавливаем metrics-server...${NC}"
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  
  # Патчим metrics-server для работы без TLS
  echo -e "${YELLOW}Настраиваем metrics-server...${NC}"
  kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
  
  echo -e "${GREEN}Metrics-server установлен и настроен!${NC}"
  
  # Ожидаем запуска metrics-server
  echo -e "${YELLOW}Ожидаем запуска metrics-server...${NC}"
  sleep 15
fi

# Применяем конфигурацию Prometheus и Grafana
echo -e "${YELLOW}Устанавливаем Prometheus...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/prometheus/

echo -e "${YELLOW}Устанавливаем Grafana...${NC}"
# Сначала dashboard configmaps
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/dashboard-configmap.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/dashboard-hpa-configmap.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/dashboard-nodes-configmap.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/dashboards.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/configmap.yaml

# Затем остальные ресурсы Grafana
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/pvc.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/deployment.yaml
kubectl apply -f /home/terra/devops/project/kubernetes/monitoring/grafana/service.yaml

echo -e "${GREEN}Мониторинг настроен и запущен!${NC}"

# Ждем, пока все поды запустятся
echo -e "${YELLOW}Ожидаем запуска всех компонентов мониторинга...${NC}"
kubectl wait --for=condition=Ready pods -l app=prometheus -n app-namespace --timeout=120s || true
kubectl wait --for=condition=Ready pods -l app=grafana -n app-namespace --timeout=120s || true

# Получаем информацию о доступе
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
PROMETHEUS_PORT=$(kubectl get svc prometheus -n app-namespace -o jsonpath='{.spec.ports[0].nodePort}')
GRAFANA_PORT=$(kubectl get svc grafana -n app-namespace -o jsonpath='{.spec.ports[0].nodePort}')

echo -e "${GREEN}"
echo "========================================================================================="
echo "Мониторинг доступен по следующим адресам:"
echo "Prometheus: http://$NODE_IP:$PROMETHEUS_PORT"
echo "Grafana: http://$NODE_IP:$GRAFANA_PORT (логин: admin, пароль: admin)"
echo "========================================================================================="
echo -e "${NC}"

echo -e "${YELLOW}Статус подов мониторинга:${NC}"
kubectl get pods -n app-namespace -l 'app in (prometheus,grafana)' 