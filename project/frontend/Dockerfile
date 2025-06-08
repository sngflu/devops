# Этап 1: Сборка
FROM node:18-alpine AS builder

WORKDIR /app

# Сначала копируем только package.json для установки зависимостей
COPY package*.json ./
RUN npm ci

# Затем копируем все остальные файлы
COPY . .

# Собираем приложение
RUN npm run build

# Этап 2: Отдача статики
FROM nginx:alpine

# Удалим дефолтную страницу nginx
RUN rm -rf /usr/share/nginx/html/*

# Копируем собранную статику
COPY --from=builder /app/dist /usr/share/nginx/html

# Настройка nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
