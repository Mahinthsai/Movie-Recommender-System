import os
import streamlit as st
import pickle
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    st.error("TMDB API key is missing! Please set it in Render environment variables.")

# ------------------------------
# Page Configuration
# ------------------------------
st.set_page_config(
    page_title="Movie Magic Recommender",
    page_icon="🍿",
    layout="wide"
)

# ------------------------------
# Session State Initialization
# ------------------------------
for key, default in [("history", []), ("mode", None), ("selected_movie", None), ("random_movie", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ------------------------------
# TMDB API & Helper Functions
# ------------------------------
def requests_retry_session(retries=5, backoff_factor=1):
    s = requests.Session()
    s.mount("http://", HTTPAdapter(max_retries=Retry(total=retries, backoff_factor=backoff_factor, status_forcelist=(500,502,504))))
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=retries, backoff_factor=backoff_factor, status_forcelist=(500,502,504))))
    return s

def fetch_poster(movie_id):
    try:
        r = requests_retry_session().get(f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}")
        return f"https://image.tmdb.org/t/p/w500{r.json().get('poster_path')}" if r.status_code==200 and r.json().get('poster_path') else None
    except: return None

def fetch_trailer(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}"
        response = requests_retry_session().get(url)
        if response.status_code == 200:
            for video in response.json().get("results", []):
                if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                    return f"https://youtu.be/{video['key']}"
    except: return None
    return None

def get_movie_details(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=credits,videos"
        r = requests_retry_session().get(url)
        if r.status_code == 200:
            data = r.json()
            directors = [c["name"] for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
            cast_list = data.get("credits", {}).get("cast", [])[:5]
            cast_details = [{"name": c.get("name"), "character": c.get("character"),
                             "profile": f"https://image.tmdb.org/t/p/w500{c['profile_path']}" if c.get("profile_path") else None} for c in cast_list]
            genres = ", ".join([g["name"] for g in data.get("genres", [])]) if data.get("genres") else "N/A"
            budget = f"${data.get('budget',0):,}" if data.get('budget',0)>0 else "N/A"
            revenue = f"${data.get('revenue',0):,}" if data.get('revenue',0)>0 else "N/A"
            available_in = ", ".join([l["english_name"] for l in data.get("spoken_languages", [])]) if data.get("spoken_languages") else "N/A"
            return {
                "rating": data.get("vote_average"),
                "vote_count": data.get("vote_count"),
                "release_date": data.get("release_date"),
                "runtime": data.get("runtime"),
                "tagline": data.get("tagline"),
                "overview": data.get("overview"),
                "director": ", ".join(directors) if directors else "N/A",
                "cast": cast_details,
                "genres": genres,
                "budget": budget,
                "revenue": revenue,
                "available_in": available_in,
            }
    except: return None

def recommend(movie):
    index = movies[movies["title"] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recs = []
    for i in distances[1:6]:
        rec_id = movies.iloc[i[0]].movie_id
        poster = fetch_poster(rec_id)
        if poster:
            recs.append({
                "title": movies.iloc[i[0]].title,
                "poster": poster,
                "trailer": fetch_trailer(rec_id)
            })
    return recs

def get_random_movie():
    rm = movies.sample(1).iloc[0]
    return {
        "title": rm["title"],
        "poster": fetch_poster(rm["movie_id"]),
        "trailer": fetch_trailer(rm["movie_id"]),
        "movie_id": rm["movie_id"]
    }

def update_history(movie_id):
    if not st.session_state.history or st.session_state.history[-1] != movie_id:
        st.session_state.history.append(movie_id)
        if len(st.session_state.history) > 5:
            st.session_state.history.pop(0)

def get_trending_movies():
    try:
        url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
        r = requests_retry_session().get(url)
        if r.status_code == 200:
            trending = r.json().get("results", [])[:5]
            return [{"title": m.get("title"), "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get("poster_path") else None, "movie_id": m.get("id")} for m in trending]
    except: return []
    return []

# ------------------------------
# Load Data
# ------------------------------
movies = pickle.load(open("model_files/movie_list.pkl", "rb"))
similarity = pickle.load(open("model_files/similarity.pkl", "rb"))

# ------------------------------
# UI Header
# ------------------------------
st.markdown("""
<h1 style='text-align:center;color:#FF4B4B;'>Let’s Find the Perfect Movie that Matches Your Vibe!🎬</h1>
<p style='text-align:center;color:#7f8c8d;'>Just pick a title and let us do the magic ✨</p>
""", unsafe_allow_html=True)
st.markdown("---")

# ------------------------------
# Trending Section
# ------------------------------
st.markdown("<h2 style='text-align:center;color:#FF4B4B;'>🔥 Now Trending</h2>", unsafe_allow_html=True)
trending_movies = get_trending_movies()
trending_cols = st.columns(5)
for idx, movie in enumerate(trending_movies):
    with trending_cols[idx]:
        if movie.get("poster"):
            st.image(movie["poster"], use_container_width=True)
        st.markdown(f"<p style='text-align:center;'>{movie['title']}</p>", unsafe_allow_html=True)

st.markdown("---")

# ------------------------------
# Main Selection Section
# ------------------------------
col_search, col_spacer, col_surprise = st.columns([3,1,2])
with col_search:
    st.subheader("🔍 Search for a Movie")
    selected_movie = st.selectbox("Type to search...", movies["title"].values, key="select_movie")
    if st.button("Show Details & Recommendations", key="show_details"):
        st.session_state.mode = "search"
        st.session_state.selected_movie = selected_movie
        st.balloons()

with col_surprise:
    st.subheader("🎭 Let the Algorithm Decide!")
    if st.button("Surprise Me!", key="surprise_me"):
        st.session_state.mode = "surprise"
        st.session_state.random_movie = get_random_movie()
        st.balloons()

# ------------------------------
# Movie Display Function
# ------------------------------
def display_movie(title, movie_id):
    update_history(movie_id)
    details = get_movie_details(movie_id)
    trailer = fetch_trailer(movie_id)
    st.markdown(f"<h2>🎬 {title}</h2>", unsafe_allow_html=True)
    colL, colR = st.columns([1,2])
    with colL:
        poster = fetch_poster(movie_id)
        if poster: st.image(poster, use_container_width=True)
    with colR:
        if details:
            st.markdown(f"**Rating:** {details.get('rating','N/A')}/10 | **Runtime:** {details.get('runtime','N/A')} mins")
            st.markdown(f"**Genres:** {details.get('genres','N/A')}")
            st.markdown(f"**Directed by:** {details.get('director','N/A')}")
            st.markdown(f"**Overview:** {details.get('overview','N/A')}")
        if trailer: st.video(trailer)

    # Recommendations
    recs = recommend(title)
    if recs:
        st.subheader("🚀 Recommended Movies")
        rec_cols = st.columns([1,1,1])
        for idx, rec in enumerate(recs):
            with rec_cols[idx % 3]:
                st.image(rec["poster"], use_container_width=True)
                st.markdown(f"<p style='text-align:center;'><strong>{rec['title']}</strong></p>", unsafe_allow_html=True)
                if rec.get("trailer"):
                    with st.expander("Trailer"):
                        st.video(rec["trailer"])

# ------------------------------
# Show Movie Details
# ------------------------------
if st.session_state.mode:
    if st.session_state.mode=="search":
        row = movies[movies["title"]==st.session_state.selected_movie].iloc[0]
        display_movie(st.session_state.selected_movie, row.movie_id)
    elif st.session_state.mode=="surprise":
        rand_data = st.session_state.random_movie
        display_movie(rand_data["title"], rand_data["movie_id"])

# ------------------------------
# Sidebar: Recently Viewed
# ------------------------------
with st.sidebar:
    st.header("🕒 Recently Viewed")
    if st.session_state.history:
        for i, hist_id in enumerate(reversed(st.session_state.history)):
            row = movies[movies["movie_id"]==hist_id].iloc[0]
            poster = fetch_poster(hist_id)
            with st.container():
                if poster: st.image(poster, width=100)
                if st.button(row["title"], key=f"hist_{hist_id}_{i}", use_container_width=True):
                    st.session_state.mode = "search"
                    st.session_state.selected_movie = row["title"]
                    st.session_state.select_movie = row["title"]
                    st.balloons()
                    st.experimental_rerun()
    else:
        st.write("No history yet.")

# ------------------------------
# Footer
# ------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;color:#888;'>Made with ♥️ by <strong>Mahinth Sai</strong></div>", unsafe_allow_html=True)
