#!/usr/bin/env bash

# Скрипт для автоматического получения admin-токена SonarQube
# Работает только при первом запуске (admin:admin)
# SonarQube должен быть доступен на localhost:9002

SONAR_HOST="http://localhost:9002"
ADMIN_USER="admin"
ADMIN_PASS="admin"
TOKEN_NAME="ci-token-$(date +%s)"
OUTPUT_FILE="sonarqube_admin_token.txt"

# Ожидание готовности SonarQube
function wait_for_sonarqube() {
  echo "Ожидание готовности SonarQube на $SONAR_HOST ..."
  until $(curl --output /dev/null --silent --head --fail "$SONAR_HOST/api/system/health" | grep 'UP' > /dev/null 2>&1); do
    sleep 5
    echo -n "."
  done
  echo -e "\nSonarQube готов!"
}

# Получение токена через API
function get_token() {
  echo "Пробуем получить токен для пользователя admin..."
  RESPONSE=$(curl -s -u "$ADMIN_USER:$ADMIN_PASS" -X POST "$SONAR_HOST/api/user_tokens/generate" -d "name=$TOKEN_NAME")
  TOKEN=$(echo "$RESPONSE" | grep -oP '"token":"\K[^"]+')
  if [[ -n "$TOKEN" ]]; then
    echo "Токен успешно получен: $TOKEN"
    echo "$TOKEN" > "$OUTPUT_FILE"
    echo "Токен сохранён в $OUTPUT_FILE"
  else
    echo "Не удалось получить токен. Возможно, пароль admin уже изменён или SonarQube не готов."
    exit 1
  fi
}

wait_for_sonarqube
get_token 