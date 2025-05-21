#!/bin/bash

# Вывод информации цветом для лучшей читаемости
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Перейти в директорию с конфигурацией
cd "$(dirname "$0")"

# Выводим информацию о тесте и подсказку по запуску мониторинга
echo -e "${GREEN}Запускаем Yandex.Tank для нагрузочного тестирования...${NC}"
echo -e "${YELLOW}Тест будет выполняться примерно 3 минуты${NC}"
echo -e "${BLUE}ВАЖНО: Для мониторинга подов и HPA запустите в другом терминале:${NC}"
echo -e "${YELLOW}  cd $(pwd) && ./monitor.sh${NC}"
echo -e "${YELLOW}Нажмите Ctrl+C для остановки тестирования${NC}"

# Запускаем Yandex.Tank
docker run \
  --network host \
  -v $(pwd):/var/loadtest \
  -v $HOME/.ssh:/root/.ssh \
  direvius/yandex-tank:latest \
  -c /var/loadtest/load.yaml

# После завершения теста показываем итоговую статистику
echo -e "\n${GREEN}Тест нагрузки завершен. Итоговая информация:${NC}"
echo -e "${BLUE}[Итоговый статус HPA]${NC}"
kubectl get hpa -n app-namespace
echo -e "\n${BLUE}[Итоговый статус подов]${NC}"
kubectl get pods -n app-namespace -l app=backend 