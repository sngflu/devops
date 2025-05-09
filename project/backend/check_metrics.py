import requests
import sys

def check_metrics_endpoint():
    """
    Проверяет доступность эндпоинта /metrics
    """
    try:
        response = requests.get('http://localhost:5174/metrics')
        if response.status_code == 200:
            print("Эндпоинт /metrics доступен!")
            print("Пример метрик:")
            print("-" * 50)
            # Выводим первые 10 строк
            lines = response.text.split('\n')
            for line in lines[:10]:
                print(line)
            print("-" * 50)
            print(f"Всего строк метрик: {len(lines)}")
        else:
            print(f"Ошибка: Эндпоинт /metrics вернул код {response.status_code}")
            print("Ответ:")
            print(response.text)
    except Exception as e:
        print(f"Ошибка при попытке обращения к /metrics: {str(e)}")

if __name__ == "__main__":
    check_metrics_endpoint() 