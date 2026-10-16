"""Indonesian provinces, used for "news from your area" and the weather box.

`code` is the ISO 3166-2:ID subdivision code (without the "ID-" prefix), which is
what IP geolocation services report as `region_code`. `aliases` are the English
names those services may report instead. `lat`/`lon` point at the provincial
capital and are used for the weather forecast when a reader picks a province by hand.
"""

from typing import Any, Dict, List

PROVINCES: List[Dict[str, Any]] = [
    {"code": "AC", "name": "Aceh", "capital": "Banda Aceh", "lat": 5.55, "lon": 95.32, "aliases": ["Aceh"]},
    {"code": "SU", "name": "Sumatera Utara", "capital": "Medan", "lat": 3.59, "lon": 98.67, "aliases": ["North Sumatra"]},
    {"code": "SB", "name": "Sumatera Barat", "capital": "Padang", "lat": -0.95, "lon": 100.35, "aliases": ["West Sumatra"]},
    {"code": "RI", "name": "Riau", "capital": "Pekanbaru", "lat": 0.51, "lon": 101.45, "aliases": ["Riau"]},
    {"code": "KR", "name": "Kepulauan Riau", "capital": "Tanjung Pinang", "lat": 0.92, "lon": 104.45, "aliases": ["Riau Islands"]},
    {"code": "JA", "name": "Jambi", "capital": "Jambi", "lat": -1.61, "lon": 103.61, "aliases": ["Jambi"]},
    {"code": "SS", "name": "Sumatera Selatan", "capital": "Palembang", "lat": -2.99, "lon": 104.76, "aliases": ["South Sumatra"]},
    {"code": "BB", "name": "Kepulauan Bangka Belitung", "capital": "Pangkal Pinang", "lat": -2.13, "lon": 106.11, "aliases": ["Bangka Belitung Islands", "Bangka-Belitung"]},
    {"code": "BE", "name": "Bengkulu", "capital": "Bengkulu", "lat": -3.80, "lon": 102.27, "aliases": ["Bengkulu"]},
    {"code": "LA", "name": "Lampung", "capital": "Bandar Lampung", "lat": -5.43, "lon": 105.26, "aliases": ["Lampung"]},
    {"code": "JK", "name": "DKI Jakarta", "capital": "Jakarta", "lat": -6.20, "lon": 106.85, "aliases": ["Jakarta", "Special Capital Region of Jakarta"]},
    {"code": "BT", "name": "Banten", "capital": "Serang", "lat": -6.12, "lon": 106.15, "aliases": ["Banten"]},
    {"code": "JB", "name": "Jawa Barat", "capital": "Bandung", "lat": -6.92, "lon": 107.61, "aliases": ["West Java"]},
    {"code": "JT", "name": "Jawa Tengah", "capital": "Semarang", "lat": -6.99, "lon": 110.42, "aliases": ["Central Java"]},
    {"code": "YO", "name": "DI Yogyakarta", "capital": "Yogyakarta", "lat": -7.80, "lon": 110.36, "aliases": ["Yogyakarta", "Special Region of Yogyakarta"]},
    {"code": "JI", "name": "Jawa Timur", "capital": "Surabaya", "lat": -7.25, "lon": 112.75, "aliases": ["East Java"]},
    {"code": "BA", "name": "Bali", "capital": "Denpasar", "lat": -8.65, "lon": 115.22, "aliases": ["Bali"]},
    {"code": "NB", "name": "Nusa Tenggara Barat", "capital": "Mataram", "lat": -8.58, "lon": 116.12, "aliases": ["West Nusa Tenggara"]},
    {"code": "NT", "name": "Nusa Tenggara Timur", "capital": "Kupang", "lat": -10.18, "lon": 123.61, "aliases": ["East Nusa Tenggara"]},
    {"code": "KB", "name": "Kalimantan Barat", "capital": "Pontianak", "lat": -0.03, "lon": 109.33, "aliases": ["West Kalimantan"]},
    {"code": "KT", "name": "Kalimantan Tengah", "capital": "Palangka Raya", "lat": -2.21, "lon": 113.92, "aliases": ["Central Kalimantan"]},
    {"code": "KS", "name": "Kalimantan Selatan", "capital": "Banjarbaru", "lat": -3.44, "lon": 114.83, "aliases": ["South Kalimantan"]},
    {"code": "KI", "name": "Kalimantan Timur", "capital": "Samarinda", "lat": -0.50, "lon": 117.15, "aliases": ["East Kalimantan"]},
    {"code": "KU", "name": "Kalimantan Utara", "capital": "Tanjung Selor", "lat": 2.84, "lon": 117.37, "aliases": ["North Kalimantan"]},
    {"code": "SA", "name": "Sulawesi Utara", "capital": "Manado", "lat": 1.47, "lon": 124.84, "aliases": ["North Sulawesi"]},
    {"code": "GO", "name": "Gorontalo", "capital": "Gorontalo", "lat": 0.54, "lon": 123.06, "aliases": ["Gorontalo"]},
    {"code": "ST", "name": "Sulawesi Tengah", "capital": "Palu", "lat": -0.90, "lon": 119.87, "aliases": ["Central Sulawesi"]},
    {"code": "SR", "name": "Sulawesi Barat", "capital": "Mamuju", "lat": -2.68, "lon": 118.89, "aliases": ["West Sulawesi"]},
    {"code": "SN", "name": "Sulawesi Selatan", "capital": "Makassar", "lat": -5.15, "lon": 119.43, "aliases": ["South Sulawesi"]},
    {"code": "SG", "name": "Sulawesi Tenggara", "capital": "Kendari", "lat": -3.99, "lon": 122.51, "aliases": ["Southeast Sulawesi"]},
    {"code": "MA", "name": "Maluku", "capital": "Ambon", "lat": -3.70, "lon": 128.18, "aliases": ["Maluku", "Moluccas"]},
    {"code": "MU", "name": "Maluku Utara", "capital": "Sofifi", "lat": 0.74, "lon": 127.56, "aliases": ["North Maluku"]},
    {"code": "PB", "name": "Papua Barat", "capital": "Manokwari", "lat": -0.86, "lon": 134.08, "aliases": ["West Papua"]},
    {"code": "PD", "name": "Papua Barat Daya", "capital": "Sorong", "lat": -0.88, "lon": 131.25, "aliases": ["Southwest Papua"]},
    {"code": "PA", "name": "Papua", "capital": "Jayapura", "lat": -2.53, "lon": 140.72, "aliases": ["Papua"]},
    {"code": "PT", "name": "Papua Tengah", "capital": "Nabire", "lat": -3.37, "lon": 135.50, "aliases": ["Central Papua"]},
    {"code": "PE", "name": "Papua Pegunungan", "capital": "Wamena", "lat": -4.10, "lon": 138.94, "aliases": ["Highland Papua", "Papua Highlands"]},
    {"code": "PS", "name": "Papua Selatan", "capital": "Merauke", "lat": -8.49, "lon": 140.40, "aliases": ["South Papua"]},
]

DEFAULT_PROVINCE_CODE = "JK"
