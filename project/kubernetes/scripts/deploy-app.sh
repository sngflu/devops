#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Развертывание приложения в Kubernetes...${NC}"

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

# Проверяем наличие StorageClass
if ! kubectl get storageclass standard > /dev/null 2>&1; then
  echo -e "${YELLOW}Создаем StorageClass standard...${NC}"
  cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
EOF
  echo -e "${GREEN}StorageClass создан!${NC}"
fi

# Создаем PersistentVolume для сервисов
echo -e "${YELLOW}Создаем PersistentVolume для PostgreSQL...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgres-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: standard
  hostPath:
    path: /mnt/data/postgres
EOF

echo -e "${YELLOW}Создаем PersistentVolume для MinIO...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: minio-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: standard
  hostPath:
    path: /mnt/data/minio
EOF

# Создаем директории на хосте для PersistentVolumes
echo -e "${YELLOW}Создаем директории на хосте для PersistentVolumes...${NC}"
sudo mkdir -p /mnt/data/postgres /mnt/data/minio
sudo chmod -R 777 /mnt/data/postgres /mnt/data/minio

# Применяем ресурсы Kubernetes
echo -e "${YELLOW}Запускаем PostgreSQL...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/postgres -n app-namespace

echo -e "${YELLOW}Запускаем MinIO...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/minio -n app-namespace

echo -e "${YELLOW}Запускаем бэкенд с HPA...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/backend -n app-namespace

echo -e "${YELLOW}Запускаем фронтенд...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/frontend -n app-namespace

echo -e "${YELLOW}Настраиваем Ingress...${NC}"
kubectl apply -f /home/terra/devops/project/kubernetes/ingress.yaml -n app-namespace

# Ждем, пока все поды запустятся
echo -e "${YELLOW}Ожидаем запуска всех компонентов...${NC}"
kubectl wait --for=condition=Ready pods --all -n app-namespace --timeout=300s || true

echo -e "${GREEN}Компоненты запущены!${NC}"

# Получаем информацию о доступе
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
BACKEND_PORT=$(kubectl get svc backend -n app-namespace -o jsonpath='{.spec.ports[0].nodePort}')
FRONTEND_PORT=$(kubectl get svc frontend -n app-namespace -o jsonpath='{.spec.ports[0].nodePort}')

echo -e "${GREEN}"
echo "========================================================================================="
echo "Приложение запущено и доступно по следующим адресам:"
echo "Frontend: http://$NODE_IP:$FRONTEND_PORT"
echo "Backend API: http://$NODE_IP:$BACKEND_PORT"
echo "========================================================================================="
echo -e "${NC}"

echo -e "${YELLOW}Статус подов:${NC}"
kubectl get pods -n app-namespace

echo -e "${YELLOW}Статус HPA:${NC}"
kubectl get hpa -n app-namespace

echo -e "${GREEN}"
echo "Для тестирования автомасштабирования вы можете использовать:"
echo "cd /home/terra/devops/project/kubernetes"
echo "./load-test-k8s.sh"
echo -e "${NC}" 