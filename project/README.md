# Приложение для анализа видео с интеграцией MinIO

## Описание

Это приложение предназначено для анализа видеозаписей, обнаружения оружия и ножей на видео и сохранения результатов. В качестве хранилища данных используется MinIO - S3-совместимое объектное хранилище.

## Требования

- Docker и Docker Compose
- Python 3.10+

## Запуск приложения

1. Клонируйте репозиторий:

   ```
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Запустите контейнеры с помощью Docker Compose:

   ```
   docker-compose up -d
   ```

3. Приложение будет доступно по адресу:
   - Backend API: http://localhost:5174
   - MinIO Console: http://localhost:9001 (логин: minioadmin, пароль: minioadmin)
   - PgAdmin: http://localhost:5050 (логин: admin@example.com, пароль: admin)

## Хранение данных в MinIO

Приложение настроено на использование MinIO в качестве основного хранилища видео и логов обработки. Это обеспечивает:

- Масштабируемость и высокую доступность
- Совместимость с AWS S3 API
- Безопасное хранение данных

### Просмотр данных в MinIO

1. Откройте консоль MinIO: http://localhost:9001
2. Войдите с учетными данными (minioadmin/minioadmin)
3. Перейдите в секцию "Buckets"
4. Вы увидите два бакета:
   - `videos` - для хранения видеофайлов
   - `logs` - для хранения логов обработки

### Миграция с локального хранилища

Если у вас есть существующие данные в локальном хранилище, вы можете мигрировать их в MinIO:

```bash
# Из корня проекта
python -m app.utils.migrate_to_minio
```

Подробную информацию о работе с MinIO можно найти в файле [backend/README_MINIO.md](backend/README_MINIO.md).

## Структура проекта

- `backend/` - Код бэкенда
  - `app/` - Код приложения
    - `api/` - API маршруты и контроллеры
    - `models/` - Модели для обнаружения объектов
    - `services/` - Сервисы приложения
      - `minio_storage.py` - Интеграция с MinIO
      - `video_storage.py` - Абстракция для работы с хранилищем
      - `video_processing.py` - Обработка видео и обнаружение объектов
  - `tests/` - Тесты
  - `utils/` - Утилиты, включая миграцию в MinIO
- `storage/` - Директория для временного локального хранения
- `docker-compose.yml` - Конфигурация Docker

## API Endpoints

- `POST /login` - Авторизация пользователя
- `POST /register` - Регистрация нового пользователя
- `POST /predict` - Загрузка и анализ видео
- `GET /videos` - Получение списка видео
- `GET /video/<filename>` - Получение видео
- `GET /video/<filename>/url` - Получение временной ссылки на видео
- `GET /videos/<filename>/logs` - Получение логов анализа видео
- `DELETE /videos/<filename>` - Удаление видео и логов
- `PUT /videos/<filename>` - Обновление информации о видео

## Решение проблем

### Проблемы с доступом к MinIO

Если возникают проблемы с доступом к MinIO:

1. Проверьте, что контейнер MinIO запущен:

   ```
   docker ps | grep minio
   ```

2. Проверьте логи MinIO:

   ```
   docker logs minio
   ```

3. Проверьте, что бэкенд имеет доступ к MinIO:
   ```
   docker exec -it backend ping minio
   ```

### Ошибки при загрузке видео

1. Проверьте, что видео имеет поддерживаемый формат (.mp4, .avi, .mov, .mkv)
2. Проверьте, что размер видео не превышает 100 МБ
3. Проверьте, что MinIO доступен и имеет достаточно места

> Примечание: Если MinIO недоступен, система автоматически сохранит видео в локальном хранилище.

# Лабораторная работа №2 - Terraform с libvirt

## Предварительные требования

Перед началом работы убедитесь, что у вас установлены:

1. libvirt и QEMU:

   ```bash
   sudo apt-get update
   sudo apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virt-manager
   ```

2. Terraform - https://www.terraform.io/downloads.html

3. WSL (Windows Subsystem for Linux) - если вы работаете в Windows

   - Для работы libvirt в WSL рекомендуется WSL2

4. Добавьте пользователя в группу libvirt:
   ```bash
   sudo usermod -aG libvirt $USER
   newgrp libvirt
   ```

## Настройка проекта

1. Создайте копию файла `terraform.tfvars.example` с именем `terraform.tfvars` и заполните необходимые параметры:

```
libvirt_uri = "qemu:///system"
vm_image_url = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64.img"
ssh_username = "ubuntu"
ssh_password = "your_password_here"
```

2. Выполните инициализацию Terraform:

```bash
terraform init
```

3. Проверьте план выполнения:

```bash
terraform plan
```

4. Разверните виртуальную машину:

```bash
terraform apply
```

5. Для удаления инфраструктуры:

```bash
terraform destroy
```

## Работа с Docker на виртуальной машине

После создания виртуальной машины Docker будет автоматически установлен.
IP-адрес виртуальной машины будет выведен в консоль после успешного применения конфигурации.

Для подключения к виртуальной машине используйте:

```bash
ssh <ssh_username>@<vm_ip>
```

## Создание Docker-образа

1. Клонируйте ваше приложение из Лабораторной работы №1 на виртуальную машину
2. Создайте Dockerfile для вашего приложения
3. Соберите образ Docker:

```bash
docker build -t myapp:latest .
```

## Сохранение образа в облачном реестре

Для сохранения образа в Docker Hub:

1. Войдите в Docker Hub:

```bash
docker login
```

2. Отметьте образ соответствующим тегом:

```bash
docker tag myapp:latest username/myapp:latest
```

3. Отправьте образ в репозиторий:

```bash
docker push username/myapp:latest
```

## Примечания

- Если вы используете WSL в Windows, убедитесь, что сервис libvirt запущен:

  ```bash
  sudo service libvirtd start
  ```

- Для проверки статуса libvirt:

  ```bash
  sudo service libvirtd status
  ```

- Если возникают проблемы с доступом, проверьте права:

  ```bash
  sudo chmod 666 /var/run/libvirt/libvirt-sock
  ```

- Для доступа к графическому интерфейсу виртуальной машины:
  ```bash
  sudo virt-manager
  ```

# Автоматизированная настройка виртуальной машины с Docker

Этот проект представляет собой автоматизированное решение для развертывания виртуальной машины с Docker через Terraform и Ansible.

## Требования

Перед началом убедитесь, что у вас установлены следующие компоненты:

- VirtualBox (6.0+)
- Terraform (1.0+)
- Ansible (2.9+)
- bash/shell
- cloud-image-utils (для создания cloud-init образа)

## Настройка и развертывание

### Автоматическое развертывание

1. Запустите скрипт setup.sh для автоматического создания ВМ:

```bash
cd project
chmod +x setup.sh
./setup.sh
```

Скрипт выполнит следующие действия:

- Проверит наличие необходимых инструментов
- Скачает образ Ubuntu 20.04 cloud image, если его нет
- Создаст cloud-init ISO для автоматизированной установки
- Создаст виртуальную машину с настроенным Docker
- Настроит все необходимые сетевые параметры и перенаправление портов
- Дождется полной загрузки виртуальной машины
- Проверит соединение через Ansible

2. После успешного выполнения скрипта setup.sh, развертывание приложения можно выполнить с помощью Ansible:

```bash
ansible-playbook -i ansible/inventory.ini ansible/deploy_project.yml
```

### Доступ к виртуальной машине

- SSH: `ssh -p 2222 ubuntu@127.0.0.1` (пароль: ubuntu)
- Веб-интерфейсы:
  - Frontend: http://127.0.0.1:5173
  - Backend: http://127.0.0.1:5174
  - PGAdmin: http://127.0.0.1:5050
  - MinIO Console: http://127.0.0.1:9001
  - MinIO API: http://127.0.0.1:9000

## Структура проекта

- `setup.sh` - основной скрипт автоматизированного развертывания
- `main.tf` - файл конфигурации Terraform (информационный)
- `cloud-init/` - директория с файлами cloud-init для автоматизированной установки
- `ansible/` - директория с playbook и ролями для настройки и развертывания
  - `deploy_project.yml` - основной playbook для развертывания приложения
  - `inventory.ini` - инвентарь Ansible
  - `roles/` - роли Ansible для Docker и развертывания

## Важные заметки

- Все пароли установлены как "ubuntu" для простоты демонстрации
- Виртуальная машина настраивается с 2 ГБ оперативной памяти и 2 ядрами CPU
- Развертывание проекта происходит в директорию /opt/myproject
- Docker и Docker Compose устанавливаются автоматически при создании ВМ

## Устранение неполадок

1. Если происходит ошибка `Missing sudo password` при запуске Ansible:

   - Убедитесь, что в inventory.ini указан параметр `ansible_become_pass=ubuntu`
   - Или запустите команду с флагом `--ask-become-pass` и введите пароль "ubuntu"

2. Если виртуальная машина не запускается:
   - Проверьте файл журнала VirtualBox для поиска ошибок
   - Убедитесь, что хост-машина имеет достаточно ресурсов
