## Состав проекта
- `api.py` — FastAPI backend.
- `movie_recommender_web/` — frontend (HTML, CSS, JavaScript).
- `artifacts/` — сохранённые данные и матрицы обученных моделей, необходимые API.
- `data/` — исходные данные MovieLens и промежуточные данные.
- `movie_recommender.ipynb` — ноутбук с подготовкой данных, обучением и оценкой моделей.
- `requirements_api.txt` — зависимости для запуска API.

## Запуск проекта
```bash
py -m pip install -r requirements_api.txt
py -m uvicorn api:app --host 127.0.0.1 --port 8000
```

```bash
py -m http.server 5500 --bind 127.0.0.1 --directory movie_recommender_web
```
