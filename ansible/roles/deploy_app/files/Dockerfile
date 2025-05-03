FROM nginx:latest

# Копируем файлы приложения
COPY . /usr/share/nginx/html

# Открываем порт 80
EXPOSE 80

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"] 