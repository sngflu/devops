#!/bin/bash

# Скрипт для развертывания системы Telegram мониторинга

set -e

echo "🚀 Развертывание системы Telegram мониторинга..."

# Проверяем наличие kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl не найден. Установите kubectl для продолжения."
    exit 1
fi

# Проверяем подключение к кластеру
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Не удается подключиться к Kubernetes кластеру."
    exit 1
fi

echo "✅ Подключение к кластеру установлено"

# Создаем namespace если его нет
echo "📦 Создание namespace lab4-app..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: lab4-app
EOF

# Применяем секрет Telegram
echo "🔐 Создание секрета Telegram..."
kubectl apply -f ../scripts/create-telegram-secret.yaml

# Проверяем, что секрет создан
if kubectl get secret telegram-secret -n lab4-app &> /dev/null; then
    echo "✅ Секрет Telegram создан успешно"
else
    echo "❌ Ошибка создания секрета Telegram"
    exit 1
fi

# Создаем kubeconfig секрет для мониторинга
echo "🔧 Создание kubeconfig секрета..."
kubectl create secret generic kubeconfig-secret \
    --from-file=config=$HOME/.kube/config \
    -n lab4-app \
    --dry-run=client -o yaml | kubectl apply -f -

# Проверяем наличие PVC для хранения данных
echo "💾 Проверка PVC для хранения данных..."
if ! kubectl get pvc app-storage-pvc -n lab4-app &> /dev/null; then
    echo "⚠️  PVC app-storage-pvc не найден, создаем..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-storage-pvc
  namespace: lab4-app
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
fi

# Применяем конфигурацию мониторинга
echo "📊 Развертывание системы мониторинга..."
kubectl apply -f ../monitoring/telegram-monitor.yaml

# Ждем готовности deployment
echo "⏳ Ожидание готовности deployment..."
kubectl rollout status deployment/telegram-monitor -n lab4-app --timeout=300s

# Проверяем статус подов
echo "🔍 Проверка статуса подов..."
kubectl get pods -n lab4-app -l app=telegram-monitor

# Показываем логи для проверки
echo "📋 Последние логи мониторинга:"
echo "--- Kubernetes Monitor ---"
kubectl logs -n lab4-app -l app=telegram-monitor -c kubernetes-monitor --tail=10 || true

echo "--- File Monitor ---"
kubectl logs -n lab4-app -l app=telegram-monitor -c file-monitor --tail=10 || true

echo ""
echo "🎉 Система Telegram мониторинга развернута успешно!"
echo ""
echo "📱 Уведомления будут отправляться в Telegram для пользователей:"
echo "   • 476313960"
echo "   • 743515206"
echo ""
echo "🔍 Мониторинг отслеживает:"
echo "   • Изменения в Kubernetes ресурсах (pods, services, deployments, ingress)"
echo "   • Изменения в файлах проекта"
echo ""
echo "📊 Для просмотра логов используйте:"
echo "   kubectl logs -n lab4-app -l app=telegram-monitor -c kubernetes-monitor -f"
echo "   kubectl logs -n lab4-app -l app=telegram-monitor -c file-monitor -f"
echo ""
echo "🛑 Для остановки мониторинга:"
echo "   kubectl delete deployment telegram-monitor -n lab4-app" 