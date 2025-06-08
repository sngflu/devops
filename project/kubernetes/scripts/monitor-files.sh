#!/bin/bash

# Скрипт для мониторинга изменений в файлах проекта
# Отправляет уведомления в Telegram о добавлении, изменении или удалении файлов

LOG_FILE="/tmp/monitor-files.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "$(date): Запуск мониторинга файлов..."

# Получаем токен и ID пользователей из секретов
TELEGRAM_BOT_TOKEN=$(kubectl get secret telegram-secret -n lab4-app -o jsonpath='{.data.token}' | base64 -d 2>/dev/null)
TELEGRAM_USER_IDS=$(kubectl get secret telegram-secret -n lab4-app -o jsonpath='{.data.user_ids}' | base64 -d 2>/dev/null)

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_USER_IDS" ]; then
    echo "Ошибка: Не удалось получить данные Telegram из секрета"
    exit 1
fi

# Директории для мониторинга
WATCH_DIRS=(
    "/app/backend"
    "/app/frontend" 
    "/app/kubernetes"
    "/app/storage"
)

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

# Функция для определения типа файла
get_file_type() {
    local file="$1"
    local extension="${file##*.}"
    
    case "$extension" in
        "py") echo "Python" ;;
        "js"|"jsx") echo "JavaScript" ;;
        "ts"|"tsx") echo "TypeScript" ;;
        "yaml"|"yml") echo "YAML" ;;
        "json") echo "JSON" ;;
        "md") echo "Markdown" ;;
        "sh") echo "Shell Script" ;;
        "Dockerfile") echo "Docker" ;;
        "sql") echo "SQL" ;;
        "css") echo "CSS" ;;
        "html") echo "HTML" ;;
        *) echo "File" ;;
    esac
}

# Функция для получения размера файла в читаемом формате
get_file_size() {
    local file="$1"
    if [ -f "$file" ]; then
        local size=$(stat -c%s "$file" 2>/dev/null || echo "0")
        if [ "$size" -gt 1048576 ]; then
            echo "$(($size / 1048576)) MB"
        elif [ "$size" -gt 1024 ]; then
            echo "$(($size / 1024)) KB"
        else
            echo "$size B"
        fi
    else
        echo "0 B"
    fi
}

# Функция обработки событий inotify
handle_event() {
    local event="$1"
    local file="$2"
    local dir="$3"
    
    # Игнорируем временные файлы, скрытые файлы и системные файлы
    if [[ "$file" =~ ^\. ]] || [[ "$file" =~ ~$ ]] || [[ "$file" =~ \.tmp$ ]] || [[ "$file" =~ \.swp$ ]] || [[ "$file" =~ \.log$ ]]; then
        return
    fi
    
    local full_path="$dir/$file"
    local relative_path="${full_path#/app/}"
    local file_type=$(get_file_type "$file")
    local file_size=$(get_file_size "$full_path")
    
    case "$event" in
        "CREATE")
            emoji="➕"
            action="СОЗДАН"
            ;;
        "DELETE")
            emoji="🗑️"
            action="УДАЛЕН"
            ;;
        "MODIFY")
            emoji="✏️"
            action="ИЗМЕНЕН"
            ;;
        "MOVE")
            emoji="📦"
            action="ПЕРЕМЕЩЕН"
            ;;
        *)
            emoji="🔄"
            action="ОБНОВЛЕН"
            ;;
    esac
    
    # Формируем сообщение в стиле CI
    MESSAGE=$(printf "%s *Файл %s*" "$emoji" "$action")
    MESSAGE+=$(printf "\n")
    MESSAGE+=$(printf "\n*Путь:* \`%s\`" "$relative_path")
    MESSAGE+=$(printf "\n*Тип:* %s" "$file_type")
    
    if [ "$event" != "DELETE" ]; then
        MESSAGE+=$(printf "\n*Размер:* %s" "$file_size")
    fi
    
    MESSAGE+=$(printf "\n*Время:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
    
    send_notification "$MESSAGE"
}

# Проверяем наличие inotifywait
if ! command -v inotifywait &> /dev/null; then
    echo "Установка inotify-tools..."
    apt-get update && apt-get install -y inotify-tools
fi

# Отправляем уведомление о запуске
STARTUP_MESSAGE=$(printf "📁 *Мониторинг файлов запущен*")
STARTUP_MESSAGE+=$(printf "\n")
STARTUP_MESSAGE+=$(printf "\n*Время запуска:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
STARTUP_MESSAGE+=$(printf "\n*Отслеживаемые директории:*")
for dir in "${WATCH_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        STARTUP_MESSAGE+=$(printf "\n  • \`%s\`" "${dir#/app/}")
    fi
done

send_notification "$STARTUP_MESSAGE"

# Функция для корректного завершения
cleanup() {
    echo "$(date): Получен сигнал завершения, останавливаем мониторинг файлов..."
    
    FINAL_MESSAGE=$(printf "🛑 *Мониторинг файлов остановлен*")
    FINAL_MESSAGE+=$(printf "\n")
    FINAL_MESSAGE+=$(printf "\n*Время остановки:* \`%s\`" "$(date '+%H:%M:%S %d.%m.%Y')")
    
    send_notification "$FINAL_MESSAGE"
    
    # Завершаем все дочерние процессы
    jobs -p | xargs -r kill
    exit 0
}

# Устанавливаем обработчик сигналов
trap cleanup SIGTERM SIGINT

# Запускаем мониторинг для каждой директории
for dir in "${WATCH_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "$(date): Запуск мониторинга для $dir"
        (
            inotifywait -m -r -e create,delete,modify,move "$dir" --format '%e %f %w' 2>/dev/null | \
            while read event file watch_dir; do
                handle_event "$event" "$file" "$watch_dir"
            done
        ) &
    else
        echo "$(date): Директория $dir не найдена, пропускаем"
    fi
done

echo "$(date): Все процессы мониторинга файлов запущены"

# Ждем завершения всех процессов
wait 