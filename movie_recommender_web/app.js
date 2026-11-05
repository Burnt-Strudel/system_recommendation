const API = "http://127.0.0.1:8000";

const grid = document.getElementById("movieGrid");
const message = document.getElementById("message");
const title = document.getElementById("resultsTitle");
const count = document.getElementById("resultCount");
const status = document.getElementById("apiStatus");

async function request(path) {
  let response;

  try {
    response = await fetch(`${API}${path}`);
  } catch (error) {
    throw new Error(
      "Не удалось связаться с API. Проверь, запущен ли сервер на http://127.0.0.1:8000 и включён ли CORS."
    );
  }

  const text = await response.text();
  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`API вернул не JSON (HTTP ${response.status}).`);
  }

  if (!response.ok) {
    throw new Error(data.detail || `Ошибка API: HTTP ${response.status}`);
  }

  return data;
}

function showMovies(movies, heading) {
  title.textContent = heading;
  count.textContent = `${movies.length} фильмов`;
  message.textContent = movies.length ? "" : "Ничего не найдено.";
  message.className = "message";
  grid.innerHTML = "";

  movies.forEach(movie => {
    const card = document.createElement("article");
    card.className = "movie-card";

    const genres = (movie.genres || []).slice(0, 3).join(" · ") || "Жанр не указан";
    const rating = movie.imdb_rating
      ? `★ ${Number(movie.imdb_rating).toFixed(1)} IMDb`
      : "";

    card.innerHTML = `
      <div class="poster"><span>✦</span></div>
      <div class="movie-info">
        <div class="movie-title"></div>
        <div class="movie-meta"></div>
        <div class="genres"></div>
        <div class="rating"></div>
      </div>`;

    card.querySelector(".movie-title").textContent = movie.title || "Без названия";
    card.querySelector(".movie-meta").textContent = movie.year || "Год неизвестен";
    card.querySelector(".genres").textContent = genres;
    card.querySelector(".rating").textContent = rating;

    if (movie.poster_url) {
      const poster = card.querySelector(".poster");
      poster.style.backgroundImage = `url("${movie.poster_url}")`;
      poster.style.backgroundSize = "cover";
      poster.style.backgroundPosition = "center";
      poster.querySelector("span").hidden = true;
    }

    grid.appendChild(card);
  });
}

function showError(error) {
  grid.innerHTML = "";
  count.textContent = "";
  message.textContent = error.message;
  message.className = "message error";
}

async function loadPopular() {
  message.className = "message";
  message.textContent = "Загружаем популярные фильмы…";

  try {
    showMovies(await request("/popular?limit=10"), "Популярные фильмы");
  } catch (error) {
    showError(error);
  }
}

document.getElementById("popularButton").addEventListener("click", loadPopular);

document.getElementById("titleForm").addEventListener("submit", async event => {
  event.preventDefault();
  const value = document.getElementById("titleInput").value.trim();
  if (!value) return;

  message.className = "message";
  message.textContent = "Ищем похожие фильмы…";

  try {
    showMovies(
      await request(`/recommend/title/${encodeURIComponent(value)}?limit=10`),
      `Похожие на «${value}»`
    );
  } catch (error) {
    showError(error);
  }
});

document.getElementById("genreForm").addEventListener("submit", async event => {
  event.preventDefault();
  const genre = document.getElementById("genreSelect").value;
  if (!genre) return;

  message.className = "message";
  message.textContent = "Подбираем фильмы…";

  try {
    showMovies(
      await request(`/recommend/genre/${encodeURIComponent(genre)}?limit=10`),
      `Жанр: ${genre}`
    );
  } catch (error) {
    showError(error);
  }
});

document.getElementById("userForm").addEventListener("submit", async event => {
  event.preventDefault();
  const id = document.getElementById("userInput").value.trim();
  if (!id) return;

  message.className = "message";
  message.textContent = "Подбираем персональные рекомендации…";

  try {
    showMovies(
      await request(`/recommend/user/${encodeURIComponent(id)}?limit=10`),
      `Рекомендации для пользователя ${id}`
    );
  } catch (error) {
    showError(error);
  }
});

async function init() {
  try {
    const health = await request("/health");
    status.classList.add("online");
    status.innerHTML = `<i></i> API работает · ${health.movies} фильмов`;
  } catch (error) {
    status.classList.remove("online");
    status.innerHTML = "<i></i> API не подключён";
    showError(error);
    return;
  }

  // Ошибка загрузки жанров больше не маскирует успешное подключение API.
  try {
    const data = await request("/genres");
    const select = document.getElementById("genreSelect");
    select.innerHTML = '<option value="">Выбери жанр</option>';

    (data.genres || []).forEach(genre => {
      const option = document.createElement("option");
      option.value = genre;
      option.textContent = genre;
      select.appendChild(option);
    });
  } catch (error) {
    const select = document.getElementById("genreSelect");
    select.innerHTML = '<option value="">Жанры недоступны</option>';
    console.error("Не удалось загрузить жанры:", error);
  }

  await loadPopular();
}

init();
