from flask import Flask
from flask_cors import CORS
import routes
import video_storage


app = Flask(__name__)
CORS(app)

# Инициализация хранилища
video_storage.init_storage()

# Регистрация маршрутов
app.register_blueprint(routes.bp)

if __name__ == "__main__":
    app.run(debug=True, port=5174)
