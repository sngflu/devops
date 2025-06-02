#!/bin/bash

# Скрипт для тестирования системы Telegram мониторинга

echo "🧪 Тестирование системы Telegram мониторинга..."

# Функция для создания тестового пода
test_pod_creation() {
    echo "➕ Тест: Создание тестового пода..."
    
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-monitoring-pod
  namespace: lab4-app
  labels:
    app: test-monitoring
spec:
  containers:
  - name: test-container
    image: nginx:alpine
    ports:
    - containerPort: 80
EOF

    echo "⏳ Ожидание создания пода..."
    sleep 15
    
    echo "✅ Тестовый под создан"
}

# Функция для изменения пода
test_pod_modification() {
    echo "✏️ Тест: Изменение пода..."
    
    kubectl label pod test-monitoring-pod -n lab4-app test=modified
    
    echo "⏳ Ожидание обработки изменения..."
    sleep 10
    
    echo "✅ Под изменен"
}

# Функция для удаления пода
test_pod_deletion() {
    echo "🗑️ Тест: Удаление тестового пода..."
    
    kubectl delete pod test-monitoring-pod -n lab4-app
    
    echo "⏳ Ожидание удаления пода..."
    sleep 10
    
    echo "✅ Тестовый под удален"
}

# Функция для создания тестового файла
test_file_creation() {
    echo "📄 Тест: Создание тестового файла..."
    
    # Получаем имя пода мониторинга
    MONITOR_POD=$(kubectl get pods -n lab4-app -l app=telegram-monitor -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$MONITOR_POD" ]; then
        kubectl exec -n lab4-app "$MONITOR_POD" -c file-monitor -- bash -c "echo 'Test file content' > /app/test-file.txt"
        
        echo "⏳ Ожидание обработки создания файла..."
        sleep 10
        
        echo "✅ Тестовый файл создан"
    else
        echo "❌ Под мониторинга не найден"
    fi
}

# Функция для изменения файла
test_file_modification() {
    echo "✏️ Тест: Изменение тестового файла..."
    
    MONITOR_POD=$(kubectl get pods -n lab4-app -l app=telegram-monitor -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$MONITOR_POD" ]; then
        kubectl exec -n lab4-app "$MONITOR_POD" -c file-monitor -- bash -c "echo 'Modified content' >> /app/test-file.txt"
        
        echo "⏳ Ожидание обработки изменения файла..."
        sleep 10
        
        echo "✅ Тестовый файл изменен"
    else
        echo "❌ Под мониторинга не найден"
    fi
}

# Функция для удаления файла
test_file_deletion() {
    echo "🗑️ Тест: Удаление тестового файла..."
    
    MONITOR_POD=$(kubectl get pods -n lab4-app -l app=telegram-monitor -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$MONITOR_POD" ]; then
        kubectl exec -n lab4-app "$MONITOR_POD" -c file-monitor -- rm -f /app/test-file.txt
        
        echo "⏳ Ожидание обработки удаления файла..."
        sleep 10
        
        echo "✅ Тестовый файл удален"
    else
        echo "❌ Под мониторинга не найден"
    fi
}

# Проверяем, что система мониторинга запущена
if ! kubectl get deployment telegram-monitor -n lab4-app &> /dev/null; then
    echo "❌ Система мониторинга не развернута. Запустите deploy-telegram-monitoring.sh сначала."
    exit 1
fi

echo "✅ Система мониторинга найдена"

# Проверяем статус подов
echo "📊 Статус подов мониторинга:"
kubectl get pods -n lab4-app -l app=telegram-monitor

echo ""
echo "🚀 Запуск тестов..."
echo "📱 Проверьте Telegram - должны приходить уведомления о каждом действии!"
echo ""

# Запускаем тесты с паузами
test_pod_creation
echo ""

test_pod_modification  
echo ""

test_pod_deletion
echo ""

test_file_creation
echo ""

test_file_modification
echo ""

test_file_deletion
echo ""

echo "🎉 Все тесты завершены!"
echo ""
echo "📱 Проверьте Telegram - вы должны были получить уведомления о:"
echo "   • Создании тестового пода"
echo "   • Изменении пода (добавление label)"
echo "   • Удалении пода"
echo "   • Создании тестового файла"
echo "   • Изменении файла"
echo "   • Удалении файла"
echo ""
echo "📋 Для просмотра логов мониторинга:"
echo "   kubectl logs -n lab4-app -l app=telegram-monitor -c kubernetes-monitor --tail=50"
echo "   kubectl logs -n lab4-app -l app=telegram-monitor -c file-monitor --tail=50" 