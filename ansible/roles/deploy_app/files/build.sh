#!/bin/bash
set -e

echo "=== Начинаем сборку Docker-образов ==="
cd /opt/myproject
docker-compose build --no-cache --progress=plain
echo "=== Сборка Docker-образов успешно завершена ==="

exit 0 