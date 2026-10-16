# kompas
Alternative frontend for kompas.id

Dressed up as **KOMPAS Online**, a news site straight out of 1997: table layouts,
Win95 bevels, a breaking-news `<marquee>`, a dial-up splash screen, blinking
`NEW!` badges, a hit counter, a reader poll, a square-wave "MIDI" jukebox,
cursor sparkles, 88x31 badges and a webring. Best viewed with Netscape
Navigator 3.0 at 800x600.

## Running

```sh
pip install -r requirements.txt
fastapi run main.py   # or: uvicorn main:app
```

## Layout

- `main.py` - FastAPI app, Kompas API client and page rendering
- `templates/layout.html` - shared page chrome (masthead, sidebars, footer)
- `static/retro.css` - the look
- `static/retro.js` - clock, hit counter, ticker, poll, jukebox, sparkles
- `static/front.js` - front page feeds, search, dial-up splash and pop-up

## Routes

| Route | Description |
| --- | --- |
| `/` | Front page (`?feed=latest\|popular\|hot` or `?q=search`) |
| `/read?permalink=...&format=html` | Article page (`format=json` for JSON) |
| `/api/article` | Article feed as JSON (`?type=popular\|hot`, `?search=`) |
| `/random` | Jump to a random story from the latest feed |
| `/healthz` | Health check |

Animations, the dial-up splash and the sparkles are switched off for visitors
who prefer reduced motion.
