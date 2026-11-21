import re
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image
from info import DREAMXBOTZ_IMAGE_FETCH, TMDB_API_KEY
from imdb import Cinemagoer


logger = logging.getLogger(__name__)
ia = Cinemagoer()
LONG_IMDB_DESCRIPTION = False

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""





Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)
async def fetch_image(url, size=(860, 1200)):
    if not DREAMXBOTZ_IMAGE_FETCH:
        logger.info("Image fetching is disabled.")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch image: {response.status}")
                    return None

                data = await response.read()
                img = Image.open(BytesIO(data))
                img = img.resize(size, Image.LANCZOS)


                out = BytesIO()
                img.save(out, format="JPEG")
                out.seek(0)
                return out

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request error in fetch_image: {e}")
    except IOError as e:
        logger.error(f"I/O error in fetch_image: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_image: {e}")

    return None


async def get_movie_details(query, id=False, file=None):
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year:
                    year = list_to_str(year[:1])
            else:
                year = None
            movieid = ia.search_movie(title.lower(), results=10)
            if not movieid:
                return None
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            if not movieid:
                movieid = filtered
            movieid = movieid[0].movieID
        else:
            movieid = query
        movie = ia.get_movie(movieid)
        ia.update(movie, info=['main', 'vote details'])
        if movie.get("original air date"):
            date = movie["original air date"]
        elif movie.get("year"):
            date = movie.get("year")
        else:
            date = "N/A"
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
        else:
            plot = movie.get('plot outline')
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
        poster_url = movie.get('full-size cover url')
        return {
            'title': movie.get('title'),
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie.get('imdbID')}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster_url': poster_url,
            'plot': plot,
            'rating': str(movie.get("rating", "N/A")),
            'url': f'https://www.imdb.com/title/tt{movieid}'
        }
    except Exception as e:
        logger.error(f"An error occurred in get_movie_details: {e}")
        return None

async def get_movie_detailsx(query, id=False, file=None):
    """Fetch movie metadata directly from TMDB API v3."""
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not configured")
        return None
    base = "https://api.themoviedb.org/3"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            params = {"api_key": TMDB_API_KEY, "language": "en-US"}
            if id:
                url = f"{base}/movie/{query}"
                params["append_to_response"] = "images,external_ids"
                params["include_image_language"] = "en,null"
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error("TMDB details failed: HTTP %s", resp.status)
                        return None
                    data = await resp.json()
            else:
                title_query = str(query).strip()
                year_match = re.search(r"\b(19|20)\d{2}\b", title_query)
                search_params = dict(params, query=re.sub(r"\b(19|20)\d{2}\b", "", title_query).strip())
                if year_match:
                    search_params["year"] = year_match.group(0)
                async with session.get(f"{base}/search/movie", params=search_params) as resp:
                    if resp.status != 200:
                        logger.error("TMDB search failed: HTTP %s", resp.status)
                        return None
                    results = (await resp.json()).get("results", [])
                if not results:
                    return None
                movie_id = results[0]["id"]
                detail_params = dict(params, append_to_response="images,external_ids", include_image_language="en,null")
                async with session.get(f"{base}/movie/{movie_id}", params=detail_params) as resp:
                    if resp.status != 200:
                        logger.error("TMDB details failed: HTTP %s", resp.status)
                        return None
                    data = await resp.json()

        image_base = "https://image.tmdb.org/t/p/original"
        backdrop_path = data.get("backdrop_path")
        poster_path = data.get("poster_path")
        backdrops = data.get("images", {}).get("backdrops", [])
        if not backdrop_path and backdrops:
            backdrop_path = backdrops[0].get("file_path")
        return {
            "title": data.get("title") or data.get("original_title"),
            "year": (data.get("release_date") or "")[:4] or None,
            "release_date": data.get("release_date"),
            "rating": round(float(data.get("vote_average") or 0), 1),
            "votes": data.get("vote_count", 0),
            "runtime": data.get("runtime"),
            "genres": [g.get("name") for g in data.get("genres", [])],
            "languages": [l.get("english_name") for l in data.get("spoken_languages", [])],
            "countries": [c.get("name") for c in data.get("production_countries", [])],
            "plot": data.get("overview"),
            "tagline": data.get("tagline"),
            "poster_url": image_base + poster_path if poster_path else None,
            "backdrop_url": image_base + backdrop_path if backdrop_path else (image_base + poster_path if poster_path else None),
            "tmdb_url": f"https://www.themoviedb.org/movie/{data.get('id')}",
            "tmdb_id": data.get("id"),
            "imdb_id": data.get("imdb_id") or data.get("external_ids", {}).get("imdb_id"),
        }
    except Exception as e:
        logger.exception("TMDB lookup failed for %s: %s", query, e)
        return None


async def create_landscape_movie_poster(backdrop_url, title, year=None, rating=None,
                                        genres=None, quality=None, language=None):
    """Create a 16:9 custom announcement image using a TMDB backdrop."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import os
    canvas_size = (1280, 720)
    try:
        if backdrop_url:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
                async with session.get(backdrop_url) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Backdrop HTTP {resp.status}")
                    raw = await resp.read()
            background = Image.open(BytesIO(raw)).convert("RGB")
        else:
            background = Image.new("RGB", canvas_size, (22, 25, 35))
        # Fill/crop to 16:9, then darken the left side for readable text.
        w, h = background.size
        scale = max(canvas_size[0] / w, canvas_size[1] / h)
        background = background.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        left = (background.width - canvas_size[0]) // 2
        top = (background.height - canvas_size[1]) // 2
        background = background.crop((left, top, left + canvas_size[0], top + canvas_size[1])).convert("RGBA")
        overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 65))
        draw_overlay = ImageDraw.Draw(overlay)
        for x in range(850):
            alpha = int(215 * (1 - x / 850))
            draw_overlay.line((x, 0, x, 720), fill=(5, 8, 15, alpha))
        background = Image.alpha_composite(background, overlay)
        draw = ImageDraw.Draw(background)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        regular_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        def font(size, bold=False):
            path = font_path if bold else regular_path
            try: return ImageFont.truetype(path, size)
            except Exception: return ImageFont.load_default()
        # Wrap title to keep it within the text-safe area.
        title = str(title or "MOVIE UPDATE").upper()
        title_font = font(64 if len(title) < 22 else 48, True)
        words, lines, line = title.split(), [], ""
        for word in words:
            candidate = (line + " " + word).strip()
            if draw.textbbox((0, 0), candidate, font=title_font)[2] > 760 and line:
                lines.append(line); line = word
            else: line = candidate
        if line: lines.append(line)
        y = 285 if len(lines) == 1 else 245
        for item in lines[:3]:
            draw.text((64, y), item, font=title_font, fill="white", stroke_width=1, stroke_fill=(0,0,0,120))
            y += 76
        meta = []
        if year: meta.append(str(year))
        if rating not in (None, "", "N/A", 0, "0"): meta.append(f"★ {rating}/10")
        if meta:
            draw.text((68, y + 12), "   •   ".join(meta), font=font(30, True), fill=(255, 215, 120, 255))
            y += 62
        if genres:
            genre_text = ", ".join(genres) if isinstance(genres, (list, tuple)) else str(genres)
            draw.text((68, y + 12), genre_text[:65], font=font(23), fill="white")
            y += 48
        extras = []
        if quality and quality != "N/A": extras.append(str(quality))
        if language and language != "N/A": extras.append(str(language))
        if extras:
            label = "  |  ".join(extras)[:75]
            draw.rounded_rectangle((62, min(y + 20, 625), 62 + min(draw.textbbox((0,0), label, font=font(22, True))[2] + 38, 760), min(y + 68, 673)), radius=18, fill=(0,0,0,175))
            draw.text((80, min(y + 30, 635)), label, font=font(22, True), fill="white")
        out = BytesIO()
        background.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
        out.seek(0)
        out.name = "movie_update.jpg"
        return out
    except Exception as e:
        logger.exception("Could not create landscape movie poster: %s", e)
        return None
