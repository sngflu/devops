#!/bin/bash

# Логирование
LOG_FILE="/tmp/monitor-changes.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "$(date): Запуск мониторинга изменений..."

# Получаем токен и ID пользователей из секретов
TELEGRAM_BOT_TOKEN=$(kubectl get secret telegram-secret -n lab4-app -o jsonpath='{.data.token}' | base64 -d 2>/dev/null)
TELEGRAM_USER_IDS=$(kubectl get secret telegram-secret -n lab4-app -o jsonpath='{.data.user_ids}' | base64 -d 2>/dev/null)

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_USER_IDS" ]; then
    echo "Ошибка: Не удалось получить данные Telegram из секрета"
    exit 1
fi

echo "Telegram бот настроен для пользователей: $TELEGRAM_USER_IDS"

# Функция для отправки уведомлений
send_notification() {
    local message="$1"
    echo "$(date): Отправка уведомления: $message"
    
    IFS=',' read -ra USER_IDS <<< "$TELEGRAM_USER_IDS"
    for user_id in "${USER_IDS[@]}"; do
        response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${user_id}" \
            -d "text=${message}" \
            -d "parse_mode=Markdown")
        
        if echo "$response" | grep -q '"ok":true'; then
            echo "✅ Уведомление отправлено пользователю $user_id"
        else
            echo "❌ Ошибка отправки пользователю $user_id: $response"
        fi
    done
}

# Функция для получения значимых полей ресурса (исключаем timestamps и статусы)
get_resource_hash() {
    local resource_type="$1"
    local namespace="$2"
    local current_state="$3"
    
    case "$resource_type" in
        "pods")
            # Для подов важны: имя, образ, фаза, но не timestamps
            echo "$current_state" | jq -r '.items[] | {name: .metadata.name, image: .spec.containers[0].image, phase: .status.phase, restarts: .status.containerStatuses[0].restartCount}' | sort
            ;;
        "services")
            # Для сервисов: имя, тип, порты
            echo "$current_state" | jq -r '.items[] | {name: .metadata.name, type: .spec.type, ports: .spec.ports}' | sort
            ;;
        "deployments")
            # Для deployment: имя, образ, реплики
            echo "$current_state" | jq -r '.items[] | {name: .metadata.name, image: .spec.template.spec.containers[0].image, replicas: .spec.replicas}' | sort
            ;;
        "ingress")
            # Для ingress: имя, хосты, правила
            echo "$current_state" | jq -r '.items[] | {name: .metadata.name, hosts: .spec.rules}' | sort
            ;;
        *)
            echo "$current_state" | jq -r '.items[] | {name: .metadata.name}' | sort
            ;;
    esac
}

# Функция для получения детальной информации о ресурсе
get_resource_details() {
    local resource_type="$1"
    local namespace="$2"
    local current_state="$3"
    
    case "$resource_type" in
        "pods")
            echo "$current_state" | jq -r '.items[] | "  • \(.metadata.name) - \(.status.phase)"'
            ;;
        "services")
            echo "$current_state" | jq -r '.items[] | "  • \(.metadata.name) - \(.spec.type)"'
            ;;
        "deployments")
            echo "$current_state" | jq -r '.items[] | "  • \(.metadata.name) - \(.status.replicas // 0)/\(.spec.replicas // 0) реплик"'
            ;;
        "ingress")
            echo "$current_state" | jq -r '.items[] | "  • \(.metadata.name) - \(.spec.rules[0].host // "no-host")"'
            ;;
        *)
            echo "$current_state" | jq -r '.items[] | "  • \(.metadata.name)"'
            ;;
    esac
}

# Функция для мониторинга изменений
monitor_changes() {
    local resource_type="$1"
    local namespace="$2"
    local previous_hash=""
    local previous_count=0
    
    echo "$(date): Начинаю мониторинг $resource_type в namespace $namespace"
    
    while true; do
        current_state=$(kubectl get "$resource_type" -n "$namespace" -o json 2>/dev/null)
        
        if [ $? -ne 0 ]; then
            echo "$(date): Ошибка получения состояния $resource_type"
            sleep 30
            continue
        fi
        
        current_count=$(echo "$current_state" | jq '.items | length' 2>/dev/null || echo "0")
        current_hash=$(get_resource_hash "$resource_type" "$namespace" "$current_state")
        
        if [ "$previous_hash" != "" ]; then
            # Проверяем только значимые изменения
            if [ "$current_count" -gt "$previous_count" ]; then
                action="СОЗДАН"
                emoji="➕"
            elif [ "$current_count" -lt "$previous_count" ]; then
                action="УДАЛЕН"
                emoji="🗑️"
            elif [ "$current_hash" != "$previous_hash" ]; then
                action="ИЗМЕНЕН"
                emoji="✏️"
            else
                # Нет значимых изменений
                previous_hash="$current_hash"
                previous_count="$current_count"
                sleep 30  # Увеличиваем интервал для уменьшения чувствительности
                continue
            fi
            
            # Формируем сообщение в стиле CI
            MESSAGE=$(printf "%s *Kubernetes %s*" "$emoji" "$action")
            MESSAGE+=$(printf "\n")
            MESSAGE+=$(printf "\n*Ресурс:* \`%s\`" "$resource_type")
            MESSAGE+=$(printf "\n*Namespace:* \`%s\`" "$namespace")
            MESSAGE+=$(printf "\n*Количество:* %d → %d" "$previous_count" "$current_count")
            MESSAGE+=$(printf "\n*Время:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
            
            # Добавляем детали только если есть ресурсы
            if [ "$current_count" -gt 0 ]; then
                MESSAGE+=$(printf "\n")
                MESSAGE+=$(printf "\n*Текущее состояние:*")
                details=$(get_resource_details "$resource_type" "$namespace" "$current_state")
                if [ -n "$details" ]; then
                    MESSAGE+=$(printf "\n%s" "$details")
                fi
            fi
            
            send_notification "$MESSAGE"
        fi
        
        previous_hash="$current_hash"
        previous_count="$current_count"
        sleep 30  # Увеличиваем интервал
    done
}

# Отправляем уведомление о запуске мониторинга
STARTUP_MESSAGE=$(printf "🚀 *Мониторинг Kubernetes запущен*")
STARTUP_MESSAGE+=$(printf "\n")
STARTUP_MESSAGE+=$(printf "\n*Время запуска:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
STARTUP_MESSAGE+=$(printf "\n*Отслеживаемые ресурсы:*")
STARTUP_MESSAGE+=$(printf "\n  • Pods")
STARTUP_MESSAGE+=$(printf "\n  • Services") 
STARTUP_MESSAGE+=$(printf "\n  • Deployments")
STARTUP_MESSAGE+=$(printf "\n  • Ingress")
STARTUP_MESSAGE+=$(printf "\n")
STARTUP_MESSAGE+=$(printf "\n*Namespace:* \`%s\`" "lab4-app")

send_notification "$STARTUP_MESSAGE"

# Запускаем мониторинг для разных типов ресурсов в фоне
monitor_changes "pods" "lab4-app" &
monitor_changes "services" "lab4-app" &
monitor_changes "deployments" "lab4-app" &
monitor_changes "ingress" "lab4-app" &

echo "$(date): Все процессы мониторинга запущены"

# Функция для корректного завершения
cleanup() {
    echo "$(date): Получен сигнал завершения, останавливаем мониторинг..."
    
    FINAL_MESSAGE=$(printf "🛑 *Мониторинг Kubernetes остановлен*")
    FINAL_MESSAGE+=$(printf "\n")
    FINAL_MESSAGE+=$(printf "\n*Время остановки:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
    
    send_notification "$FINAL_MESSAGE"
    
    # Завершаем все дочерние процессы
    jobs -p | xargs -r kill
    exit 0
}

# Устанавливаем обработчик сигналов
trap cleanup SIGTERM SIGINT

# Ждем завершения всех процессов
wait 