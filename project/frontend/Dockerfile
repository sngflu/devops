FROM node:18

WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем конфигурацию vite
COPY vite.config.js ./

# Копируем все остальные файлы проекта
COPY . .

# Проверяем, что vite установлен и работает
RUN npx vite --version

# Открываем порт
EXPOSE 5173

# Используем npx для запуска
CMD ["npx", "vite", "--host", "0.0.0.0"]