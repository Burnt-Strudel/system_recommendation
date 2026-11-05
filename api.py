import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
ART_DIR = BASE_DIR / "artifacts"

REQUIRED_FILES = [
    "movies.csv",
    "content_sim.npy",
    "cf_pred.npy",
    "r_seen.npy",
    "user_ids.npy",
    "meta.json",
]

missing = [name for name in REQUIRED_FILES if not (ART_DIR / name).is_file()]
if missing:
    raise RuntimeError(
        "Не найдены файлы модели в папке artifacts: "
        + ", ".join(missing)
        + ". Убедитесь, что папка artifacts загружена из GitHub."
    )

movies = pd.read_csv(ART_DIR / "movies.csv")


def parse_genres(value):
    """Поддерживает JSON-строки и строки со списками Python."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or pd.isna(value):
        return []

    raw = str(value).strip()
    if not raw:
        return []

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (ValueError, SyntaxError, json.JSONDecodeError):
            pass

    # Запасной вариант для CSV, где жанры сохранены через |
    return [part.strip() for part in raw.split("|") if part.strip()]


required_columns = {"title", "year", "imdb_rating", "wr", "genre_list"}
missing_columns = required_columns - set(movies.columns)
if missing_columns:
    raise RuntimeError(
        "В artifacts/movies.csv отсутствуют столбцы: "
        + ", ".join(sorted(missing_columns))
    )

movies["genre_list"] = movies["genre_list"].apply(parse_genres)
if "poster_url" not in movies.columns:
    movies["poster_url"] = ""

content_sim = np.load(ART_DIR / "content_sim.npy")
cf_pred = np.load(ART_DIR / "cf_pred.npy")
r_seen = np.load(ART_DIR / "r_seen.npy")
user_ids = np.load(ART_DIR / "user_ids.npy")
meta = json.loads((ART_DIR / "meta.json").read_text(encoding="utf-8"))

movie_count = len(movies)
if content_sim.shape != (movie_count, movie_count):
    raise RuntimeError("Размер content_sim.npy не совпадает с artifacts/movies.csv.")
if cf_pred.ndim != 2 or r_seen.ndim != 2:
    raise RuntimeError("cf_pred.npy и r_seen.npy должны быть двумерными массивами.")
if cf_pred.shape[1] != movie_count or r_seen.shape[1] != movie_count:
    raise RuntimeError("Число фильмов в CF-моделях не совпадает с movies.csv.")
if cf_pred.shape[0] != len(user_ids) or r_seen.shape[0] != len(user_ids):
    raise RuntimeError("Число пользователей в CF-моделях не совпадает с user_ids.npy.")

app = FastAPI(
    title="Movie Recommender API",
    description="API рекомендательной системы фильмов",
    version="1.0.0",
)

# Frontend запускается отдельно на localhost:5500, API — на localhost:8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def pack(indices, scores=None):
    result = []
    for pos, idx in enumerate(indices):
        row = movies.iloc[int(idx)]
        year = row["year"]
        rating = row["imdb_rating"]
        poster = row.get("poster_url", "")

        item = {
            "title": str(row["title"]),
            "year": None if pd.isna(year) else int(year),
            "genres": list(row["genre_list"]),
            "imdb_rating": None if pd.isna(rating) else float(rating),
            "poster_url": "" if pd.isna(poster) else str(poster),
        }
        if scores is not None:
            score = float(scores[pos])
            item["score"] = None if not np.isfinite(score) else round(score, 4)
        result.append(item)
    return result


def find_title(title):
    names = movies["title"].fillna("").astype(str).str.lower()
    query = title.strip().lower()

    exact = names[names == query]
    if len(exact):
        return int(exact.index[0])

    contains = names[names.str.contains(re.escape(query), regex=True)]
    if len(contains):
        return int(contains.index[0])

    raise HTTPException(status_code=404, detail=f"Фильм '{title}' не найден")


@app.get("/")
def home():
    return {
        "name": "Movie Recommender API",
        "docs": "/docs",
        "help": "/help",
        "methods": [
            "/popular",
            "/recommend/genre/{genre}",
            "/recommend/title/{title}",
            "/recommend/user/{user_id}",
        ],
    }


@app.get("/help")
def help_api():
    return {
        "GET /popular": "Топ-10 популярных фильмов по взвешенному рейтингу.",
        "GET /recommend/genre/{genre}": "10 фильмов выбранного жанра.",
        "GET /recommend/title/{title}": "10 похожих фильмов по названию.",
        "GET /recommend/user/{user_id}": "10 рекомендаций пользователю по коллаборативной фильтрации.",
        "Параметр limit": "Количество результатов от 1 до 10. По умолчанию 10.",
        "GET /genres": "Список доступных жанров.",
        "GET /health": "Проверка работы API.",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "movies": int(len(movies)),
        "content_model": meta.get("content_model"),
        "collaborative_model": meta.get("cf_model"),
    }


@app.get("/genres")
def get_genres():
    genres = sorted({genre for row in movies["genre_list"] for genre in row})
    return {"genres": genres}


@app.get("/popular")
def popular(limit: int = Query(default=10, ge=1, le=10)):
    ranked = movies.sort_values("wr", ascending=False).head(limit)
    return pack(ranked.index)


@app.get("/recommend/genre/{genre}")
def recommend_genre(genre: str, limit: int = Query(default=10, ge=1, le=10)):
    selected = movies["genre_list"].apply(
        lambda genres: genre.strip().lower() in [g.lower() for g in genres]
    )
    if not selected.any():
        raise HTTPException(status_code=404, detail=f"Жанр '{genre}' не найден")

    ranked = movies[selected].sort_values("wr", ascending=False).head(limit)
    return pack(ranked.index, ranked["wr"].to_numpy())


@app.get("/recommend/title/{title}")
def recommend_title(title: str, limit: int = Query(default=10, ge=1, le=10)):
    idx = find_title(title)
    scores = content_sim[idx].copy()
    scores[idx] = -1
    indices = np.argsort(-scores)[:limit]
    return pack(indices, scores[indices])


@app.get("/recommend/user/{user_id}")
def recommend_user(user_id: int, limit: int = Query(default=10, ge=1, le=10)):
    positions = np.where(user_ids.astype(int) == int(user_id))[0]
    if len(positions) == 0:
        raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")

    user_idx = int(positions[0])
    scores = np.where(r_seen[user_idx] > 0, -np.inf, cf_pred[user_idx])
    indices = np.argsort(-scores)[:limit]
    return pack(indices, scores[indices])
