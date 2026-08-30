#!/usr/bin/env python3
"""pwk - kids activities in Portugal, from portugalwithkids.pt

Unofficial. Reads the site's public WordPress REST API. Places carry lat/lng, so
we cache them and filter by radius; the site's own search matches words rather
than locations and misses most of what is actually nearby.
"""
import argparse, datetime as dt, html, json, math, os, re, sys, time, unicodedata
import urllib.request, urllib.error

BASE = "https://portugalwithkids.pt/wp-json"
VERSION = "1.0.0"
UA = f"pwk/{VERSION} (+https://github.com/jgalea/pwk)"
CACHE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "cache")
STALE_DAYS = 30

ORIGINS = {
    "lisbon": (38.7223, -9.1393), "lisboa": (38.7223, -9.1393),
    "porto": (41.1579, -8.6291), "cascais": (38.6979, -9.4215),
    "estoril": (38.7057, -9.3977), "carcavelos": (38.6807, -9.3350),
    "sintra": (38.7992, -9.3883), "oeiras": (38.6979, -9.3018),
    "ericeira": (38.9631, -9.4159), "setubal": (38.5244, -8.8882),
    "coimbra": (40.2033, -8.4103), "braga": (41.5454, -8.4265),
    "aveiro": (40.6405, -8.6538), "faro": (37.0194, -7.9304),
    "albufeira": (37.0891, -8.2503), "lagos": (37.1028, -8.6731),
    "funchal": (32.6669, -16.9241), "evora": (38.5714, -7.9135),
    "guimaraes": (41.4425, -8.2918), "viseu": (40.6566, -7.9125),
}
DEFAULT_ORIGIN = os.environ.get("PWK_ORIGIN", "lisbon")

# Event venues have no coordinates, only a city name, so the region filter for
# `events` is a city list rather than a radius.
REGIONS = {
    "cascais": ["cascais", "estoril", "alcabideche", "parede", "carcavelos",
                "sao domingos de rana", "s. domingos de rana"],
    "lisbon": ["lisboa", "lisbon", "oeiras", "amadora", "queluz", "algés",
               "alges", "belém", "belem", "loures", "odivelas", "sintra"],
}
REGIONS["all"] = None

# My classification, not the site's: it has no indoor/outdoor field.
INDOOR = ["museu", "oficina", "escape room", "ludoteca", "biblioteca", "aquário",
          "aquario", "ciência", "ciencia", "planetári", "planetari", "jogo de tabuleiro",
          "café de jogos", "livraria", "bowling", "pista de gelo", "teatro",
          "trampolins", "exposi", "area infantil", "área infantil", "skydiving"]
OUTDOOR = ["parque infantil", "ar livre", "praia", "parques e jardins", "quinta",
           "passadiços", "passadicos", "trilho", "natureza", "montanha", "miradouro",
           "baloiço", "baloico", "parque aventura", "escalada", "equitação", "equitacao",
           "castelo", "jardim zoológico", "área desportiva", "arte urbana"]

ALIASES = {
    "playground": "parque infantil", "beach": "praia", "farm": "quinta",
    "museum": "museu", "pool": "piscina", "waterpark": "parque aquático",
    "zoo": "zoo", "aquarium": "aquário", "workshop": "oficina", "castle": "castelo",
    "garden": "parques e jardins", "park": "parques e jardins",
    "themepark": "parque de diversões", "trampoline": "trampolins",
    "horse": "equitação", "science": "ciência", "library": "biblioteca",
    "restaurant": "restaurante", "hotel": "hot", "outdoors": "ar livre",
    "dinosaur": "dinossauro", "climbing": "escalada", "trail": "trilho",
    "minigolf": "golfe", "boat": "barco", "theatre": "teatro", "theater": "teatro",
}


def fold(s):
    s = unicodedata.normalize("NFKD", html.unescape(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def clean(s, limit=None):
    s = html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:limit] + "…" if limit and len(s) > limit else s


# ---------- cache ----------

def fetch_all(endpoint, per_page=100):
    out, page = [], 1
    while True:
        batch = get(f"{BASE}/wp/v2/{endpoint}?per_page={per_page}&page={page}")
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.3)
    return out


def refresh(quiet=False):
    os.makedirs(CACHE, exist_ok=True)
    cats = {c["id"]: html.unescape(c["name"]) for c in fetch_all("place-categories")}
    raw = fetch_all("place")
    if not raw:
        sys.exit("refresh got 0 places - refusing to overwrite the cache")
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    places, nocoord = [], 0
    for p in raw:
        loc = p.get("golo-place_location") or {}
        try:
            lat, lng = [float(x) for x in loc.get("location", "").split(",")]
        except (ValueError, AttributeError):
            nocoord += 1
            continue
        hours = {d: (p.get(f"golo-opening_{d}_time") or "").strip() for d in days}
        places.append({
            "title": clean(p["title"]["rendered"]),
            "slug": p["slug"], "link": p["link"],
            "lat": lat, "lng": lng,
            "address": loc.get("address", ""),
            "categories": [cats.get(c, str(c)) for c in p.get("place-categories", [])],
            "excerpt": clean(p.get("excerpt", {}).get("rendered", ""), 400),
            "price_band": p.get("golo-place_price_range", ""),
            "price_from": (p.get("golo-place_price_short") or "").strip(),
            "prices": clean(p.get("golo-prices", ""), 600),
            "hours": {d: h for d, h in hours.items() if h},
            "website": p.get("golo-place_website", ""),
            "phone": p.get("golo-place_phone", ""),
            "views": int(p.get("golo-place_views_count") or 0),
        })
    json.dump({"fetched": dt.date.today().isoformat(), "places": places,
               "categories": sorted(set(cats.values()))},
              open(f"{CACHE}/places.json", "w"), ensure_ascii=False, indent=1)
    if not quiet:
        msg = f"cached {len(places)} places, {len(set(cats.values()))} categories"
        print(msg + (f" ({nocoord} skipped: no coordinates)" if nocoord else ""))


def load():
    path = f"{CACHE}/places.json"
    if not os.path.exists(path):
        print("no cache yet, fetching...", file=sys.stderr)
        refresh(quiet=True)
    d = json.load(open(path))
    age = (dt.date.today() - dt.date.fromisoformat(d["fetched"])).days
    if age > STALE_DAYS:
        print(f"cache is {age} days old - run `pwk refresh`", file=sys.stderr)
    return d


# ---------- places ----------

def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = (0.5 - math.cos((la2 - la1) * p) / 2
         + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(h))


def bucket(cats, words):
    return any(w in fold(c) for c in cats for w in words)


def resolve_origin(name):
    if "," in name:
        try:
            lat, lng = [float(x) for x in name.split(",", 1)]
            return lat, lng
        except ValueError:
            sys.exit(f"could not read '{name}' as lat,lng")
    o = ORIGINS.get(fold(name))
    if not o:
        sys.exit(f"unknown origin '{name}'. Use lat,lng or one of: "
                 + ", ".join(sorted(ORIGINS)))
    return o


def cmd_near(a):
    d = load()
    origin = resolve_origin(a.origin)
    term = fold(ALIASES.get(fold(a.category), a.category)) if a.category else ""
    kw = fold(a.keyword)
    hits = []
    for p in d["places"]:
        dist = km(origin, (p["lat"], p["lng"]))
        if dist > a.radius:
            continue
        if term and not any(term in fold(c) for c in p["categories"]):
            continue
        if kw and kw not in fold(p["title"] + " " + p["address"] + " "
                                + " ".join(p["categories"]) + " " + p["excerpt"]):
            continue
        if a.free and p["price_band"] != "0":
            continue
        if a.indoor and not bucket(p["categories"], INDOOR):
            continue
        if a.outdoor and not bucket(p["categories"], OUTDOOR):
            continue
        hits.append((dist, p))
    hits.sort(key=lambda x: x[0])
    for dist, p in hits[:a.limit]:
        tag = " ·free" if p["price_band"] == "0" else (f" ·from €{p['price_from']}"
                                                       if p["price_from"] else "")
        print(f"{dist:5.1f}km  {p['title']}{tag}")
        print(f"         {', '.join(dict.fromkeys(p['categories']))[:90]}")
        if p["address"]:
            print(f"         {p['address']}")
        print(f"         {p['link']}")
    scope = f"{a.radius:g}km of {a.origin.title()}"
    print(f"\n{len(hits)} of {len(d['places'])} places within {scope}"
          f" (showing {min(a.limit, len(hits))})")


def cmd_show(a):
    d = load()
    q = fold(a.query)
    exact = [p for p in d["places"] if q == fold(p["title"]) or q == p["slug"]]
    hits = exact or [p for p in d["places"] if q in fold(p["title"])]
    if not hits:
        sys.exit(f"no place matching '{a.query}' in the cache of {len(d['places'])}")
    if len(hits) > 1 and not exact:
        print(f"{len(hits)} matches:")
        for p in hits[:15]:
            print(f"  {p['title']}  ({p['slug']})")
        return
    p = hits[0]
    print(p["title"])
    print("=" * len(p["title"]))
    print(", ".join(dict.fromkeys(p["categories"])))
    if p["address"]:
        print(f"\n{p['address']}")
    print(f"map: https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lng']}")
    home = resolve_origin(DEFAULT_ORIGIN)
    print(f"     {km(home, (p['lat'], p['lng'])):.1f}km from {DEFAULT_ORIGIN.title()}")
    if p["excerpt"]:
        print(f"\n{p['excerpt']}")
    if p["hours"]:
        print("\nopening hours:")
        for day, h in p["hours"].items():
            print(f"  {day.title():10s} {h}")
    if p["prices"]:
        print(f"\nprices:\n  {p['prices']}")
    elif p["price_from"]:
        print(f"\nfrom €{p['price_from']}")
    elif p["price_band"] == "0":
        print("\nfree")
    for label, val in (("phone", p["phone"]), ("website", p["website"])):
        if val:
            print(f"{label}: {val}")
    print(f"listing: {p['link']}")


def cmd_cats(a):
    d = load()
    origin = resolve_origin(a.origin)
    counts = {}
    for p in d["places"]:
        if km(origin, (p["lat"], p["lng"])) <= a.radius:
            for c in dict.fromkeys(p["categories"]):
                counts[c] = counts.get(c, 0) + 1
    if not counts:
        sys.exit(f"no places within {a.radius:g}km of {a.origin}")
    for c, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"{n:4d}  {c}")
    print(f"\n{len(counts)} categories within {a.radius:g}km of {a.origin.title()}")


# ---------- events ----------

def window(when):
    today = dt.date.today()
    if when == "today":
        return today, today
    if when == "tomorrow":
        return today + dt.timedelta(1), today + dt.timedelta(1)
    if when == "weekend":
        wd = today.weekday()
        if wd == 5:                      # already Saturday
            return today, today + dt.timedelta(1)
        if wd == 6:                      # Sunday: the weekend is today
            return today, today
        sat = today + dt.timedelta(5 - wd)
        return sat, sat + dt.timedelta(1)
    if when == "week":
        return today, today + dt.timedelta(7)
    if when == "month":
        return today, today + dt.timedelta(30)
    if ":" in when:
        a, b = when.split(":", 1)
        return dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return dt.date.fromisoformat(when), dt.date.fromisoformat(when)


def cmd_events(a):
    start, end = window(a.when)
    cities = REGIONS.get(a.where.lower(), REGIONS["cascais"]) if a.where.lower() in REGIONS \
        else [fold(a.where)]
    kw = fold(a.keyword)
    events, page, total = [], 1, None
    while page <= 20:
        url = (f"{BASE}/tribe/events/v1/events?per_page=50&page={page}"
               f"&start_date={start}&end_date={end}%2023:59:59")
        try:
            d = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            raise
        total = d.get("total", 0) if total is None else total
        batch = d.get("events", [])
        if not batch:
            break
        events.extend(batch)
        if len(events) >= d.get("total", 0):
            break
        page += 1
        time.sleep(0.3)
    seen, rows = set(), []
    for e in events:
        v = e.get("venue") or {}
        city = clean(v.get("city") or "")
        if cities is not None and not any(c in fold(city) for c in cities):
            continue
        title = clean(e.get("title"))
        blob = fold(title + " " + " ".join(c.get("name", "") for c in e.get("categories", [])))
        if kw and kw not in blob:
            continue
        key = (title, e.get("start_date", "")[:10])
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "date": e.get("start_date", "")[:10], "title": title, "city": city,
            "venue": clean(v.get("venue") or ""), "cost": clean(e.get("cost") or ""),
            "cats": [clean(c.get("name")) for c in e.get("categories", [])],
            "url": e.get("url", ""),
        })
    rows.sort(key=lambda r: (r["date"], r["city"], r["title"]))
    for r in rows[:a.limit]:
        cost = f"  ·{r['cost']}" if r["cost"] else "  ·free/na"
        print(f"{r['date']}  {r['title']}{cost}")
        loc = " · ".join(x for x in (r["venue"], r["city"]) if x)
        print(f"            {loc}")
        if r["cats"]:
            print(f"            {', '.join(r['cats'])}")
        print(f"            {r['url']}")
    where = a.where.title() if a.where.lower() != "all" else "Portugal"
    print(f"\n{len(rows)} events in {where}, {start} to {end}"
          f" (of {total or len(events)} nationally; showing {min(a.limit, len(rows))})")


def main():
    ap = argparse.ArgumentParser(
        prog="pwk",
        description="kids activities in Portugal, from portugalwithkids.pt (unofficial)")
    ap.add_argument("--version", action="version", version=f"pwk {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("near", help="places near a point, nearest first")
    n.add_argument("-r", "--radius", type=float, default=25, help="km (default 25)")
    n.add_argument("-c", "--category", default="", help="category, PT or EN alias")
    n.add_argument("-k", "--keyword", default="")
    n.add_argument("-o", "--origin", default=DEFAULT_ORIGIN,
                   help="town name or lat,lng (default $PWK_ORIGIN or lisbon)")
    n.add_argument("-n", "--limit", type=int, default=20)
    n.add_argument("--free", action="store_true", help="free entry only")
    n.add_argument("--indoor", action="store_true", help="rainy day (my classification)")
    n.add_argument("--outdoor", action="store_true")
    n.set_defaults(fn=cmd_near)

    e = sub.add_parser("events", help="dated events")
    e.add_argument("-w", "--when", default="weekend",
                   help="today|tomorrow|weekend|week|month|YYYY-MM-DD[:YYYY-MM-DD]")
    e.add_argument("--where", default="all", help="lisbon|cascais|porto|all|<city>")
    e.add_argument("-k", "--keyword", default="")
    e.add_argument("-n", "--limit", type=int, default=25)
    e.set_defaults(fn=cmd_events)

    s = sub.add_parser("show", help="full detail for one place")
    s.add_argument("query")
    s.set_defaults(fn=cmd_show)

    c = sub.add_parser("cats", help="categories available near you, with counts")
    c.add_argument("-r", "--radius", type=float, default=30)
    c.add_argument("-o", "--origin", default=DEFAULT_ORIGIN)
    c.set_defaults(fn=cmd_cats)

    r = sub.add_parser("refresh", help="re-pull the place cache")
    r.set_defaults(fn=lambda a: refresh())

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
