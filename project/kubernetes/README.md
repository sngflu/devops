# Запуск проекта в Kubernetes (Minikube) на macOS

В этом руководстве описано, как запустить проект в локальном Kubernetes-кластере с использованием Minikube на macOS.

## Требования

- macOS
- Docker Desktop
- Minikube
- kubectl
- Helm (опционально, для удобной установки ingress-контроллера)

## Установка необходимых инструментов

### 1. Docker Desktop

Если у вас еще не установлен Docker Desktop, скачайте его с [официального сайта](https://www.docker.com/products/docker-desktop) и установите.

### 2. Minikube

Установите Minikube с помощью Homebrew:

```bash
brew install minikube
```

### 3. kubectl

Установите kubectl с помощью Homebrew:

```bash
brew install kubectl
```

### 4. Helm (опционально)

```bash
brew install helm
```

## Запуск Minikube

1. Запустите Minikube:

```bash
minikube start --driver=docker --cpus=4 --memory=9000 --disk-size=10g
```

2. Включите необходимые дополнения:

```bash
minikube addons enable ingress
minikube addons enable metrics-server
```

3. Проверьте, что Minikube работает:

```bash
minikube status
```

## Сборка и публикация Docker-образов

1. Проверьте, что локальный Docker использует Minikube:

```bash
eval $(minikube docker-env)
```

2. Выполните скрипт для сборки образов:

```bash
./build-images.sh
```

## Деплой приложения в Kubernetes

1. Создайте namespace:

```bash
kubectl apply -f namespace.yaml
```

2. Примените все остальные манифесты:

```bash
kubectl apply -f postgres/
kubectl apply -f minio/
kubectl apply -f backend/
kubectl apply -f frontend/
kubectl apply -f monitoring/
kubectl apply -f ingress.yaml
```

3. Проверьте состояние подов:

```bash
kubectl get pods -n app-namespace
```

## Настройка доступа

1. Добавьте запись в файл `/etc/hosts`:

```
# Добавьте эту строку в /etc/hosts
127.0.0.1 app.local
```

2. Настройте перенаправление портов для Ingress:

```bash
minikube tunnel
```

Теперь ваше приложение доступно по адресу:
- Фронтенд: http://app.local
- Бэкенд API: http://app.local/api
- Prometheus: http://app.local/prometheus
- Grafana: http://app.local/grafana
- MinIO консоль: http://app.local/minio

## Тестирование автомасштабирования

Для проверки горизонтального масштабирования можно использовать инструмент `hey` для нагрузочного тестирования:

```bash
# Установка hey
brew install hey

# Запуск нагрузочного теста
hey -z 2m -c 50 http://app.local/api
```

После этого проверьте как меняется количество подов бэкенда:

```bash
kubectl get hpa -n app-namespace
kubectl get pods -n app-namespace
```

## Мониторинг

Мониторинг приложения настроен с использованием Prometheus и Grafana:

- Prometheus собирает метрики со всех подов
- Grafana используется для визуализации метрик
- Предустановленный дашборд показывает использование CPU и запросы по подам

## Очистка ресурсов

Для удаления всех ресурсов:

```bash
kubectl delete namespace app-namespace
```

Для остановки Minikube:

```bash
minikube stop
```

Для удаления Minikube:

```bash
minikube delete
``` 