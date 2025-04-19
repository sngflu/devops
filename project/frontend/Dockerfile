FROM node:18

WORKDIR /app

COPY . ./
RUN npm install

# Открываем порт
EXPOSE 5173

# Запускаем Vite
CMD ["npx", "vite", "--host", "0.0.0.0"]
