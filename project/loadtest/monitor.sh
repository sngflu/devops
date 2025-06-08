#!/bin/bash

# Вывод информации цветом для лучшей читаемости
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Количество секунд между обновлениями
INTERVAL=10

# Функция для мониторинга подов и HPA
monitor_kubernetes() {
  echo -e "${GREEN}Начинаем мониторинг подов и HPA...${NC}"
  echo -e "${YELLOW}Нажмите Ctrl+C для остановки мониторинга${NC}"
  
  while true; do
    echo -e "\n${YELLOW}============ $(date) ============${NC}"
    
    # Получаем информацию о HPA
    echo -e "${BLUE}[HPA статус]${NC}"
    sudo kubectl get hpa -n lab4-app
    
    # Получаем подробную информацию о HPA (метрики)
    echo -e "\n${BLUE}[HPA метрики]${NC}"
    sudo kubectl describe hpa -n lab4-app | grep -A 2 "Metrics:" | grep -v "Deployment pods"
    
    # Получаем информацию о подах
    echo -e "\n${BLUE}[Статус подов]${NC}"
    sudo kubectl get pods -n lab4-app -l app=backend
    
    # Получаем информацию о ресурсах подов
    echo -e "\n${BLUE}[Использование ресурсов подов]${NC}"
    sudo kubectl top pods -n lab4-app -l app=backend 2>/dev/null || echo "Метрики использования ресурсов недоступны"
    
    # Пауза между обновлениями
    sleep $INTERVAL
  done
}

# Запускаем мониторинг
monitor_kubernetes 