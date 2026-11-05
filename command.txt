py -m pip install -r requirements_api.txt

py -m uvicorn api:app --host 127.0.0.1 --port 8000

py -m http.server 5500 --bind 127.0.0.1 --directory movie_recommender_web

http://127.0.0.1:5500
