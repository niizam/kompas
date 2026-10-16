# kompas
Alternative frontend for kompas.id

Dressed up as **KOMPAS Online**, a news portal straight out of the late 90s, packed
as tightly as the great Japanese web portals of the era: colored category tabs, a
breaking-news `<marquee>`, trending keywords, tabbed headline boxes, access rankings,
a Yahoo!-style category directory, blinking `NEW!` icons, a hit counter, a reader
poll, cursor sparkles, 88x31 badges and a webring.

Widgets:

- **News from your area**: guesses your province from your IP address and shows
  local news (e.g. a search for "Jawa Timur"). You can pick another province.
- **Weather**: today and the next two days for your area.
- **News calendar**: click a day to read that day's news. Sundays and Indonesian
  public holidays are red, Saturdays blue.
- **Topic sections**: the latest from Politik, Ekonomi, Olahraga, Internasional,
  Iptek and Budaya.

Third-party services, all free and keyless, are called from the visitor's browser:
[ipwho.is](https://ipwho.is) (IP location), [Open-Meteo](https://open-meteo.com)
(weather) and [Nager.Date](https://date.nager.at) (public holidays). The calendar is
[flatpickr](https://flatpickr.js.org), vendored in `static/vendor/flatpickr`.

## Running

```sh
pip install -r requirements.txt
fastapi run main.py   # or: uvicorn main:app
```

## Layout

- `main.py`: FastAPI app, Kompas API client (with a 2-minute cache), RSS and page rendering
- `regions.py`: Indonesian provinces with ISO codes and capital coordinates
- `templates/layout.html`: shared page chrome (header, tabs, sidebars, footer)
- `templates/llms.txt`: the guide served at `/llms.txt`
- `static/retro.css`: the look
- `static/retro.js`: clock, counter, ticker, rankings, trending keywords, location, weather, calendar, poll
- `static/front.js`: front page views, topics box, regional news, topic sections

## Routes

| Route | Description |
| --- | --- |
| `/` | Front page. `?feed=latest\|popular\|hot`, `?q=search`, `?date=YYYY-MM-DD`, `&page=N` |
| `/read?permalink=...&format=html` | Article page (`format=json` for JSON) |
| `/api/article` | Articles as JSON: `?type=popular\|hot`, `?search=`, `?date=`, `?from=`/`?to=`, `?page=` |
| `/api/regions` | Indonesian provinces |
| `/rss.xml` | RSS 2.0: `?feed=`, `?q=` or `?date=` |
| `/llms.txt` | How to navigate the site and use the API, for LLMs |
| `/random` | Jump to a random story from the latest feed |
| `/docs` | Interactive API docs |
| `/healthz` | Health check |

Animations and sparkles are switched off for visitors who prefer reduced motion.
