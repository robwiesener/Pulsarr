PULSARR — PROJECTOVERDRACHT v04
(vervangt v03; bijgewerkt na app/-rename, platte screens/ en Spotweb-hardening)

Laatst bijgewerkt: 16 november 2026
Huidige code-tag: v0.9.7 + 3 commits (b2fafaa)


==================================================
0. CHANGELOG EN GEBRUIK VAN DIT DOCUMENT
==================================================

CHANGELOG
---------
v02 → v03
- Security-hoofdstuk toegevoegd (Cloudflare Access + LAN-bypass).
- Library-functionaliteit en -sync uitgebreid beschreven.
- Zoeklogica herschreven (full/title/author/background).
- Openstaande-punten-lijst geconsolideerd.
- Delta-sectie toegevoegd.

v03 → v04
- Bestandsstructuur: src/ → app/ (Zkr-conventie).
- Screens platgeslagen: app/screens/<naam>.html +
  app/screens/<naam>_routes.py (geen submappen meer).
- Gedeelde Jinja2Templates in app/templates.py.
- Spotweb-hardening: _parse_xml_response en _safe_error_message.
- Roadmap naar Zkr-alignment toegevoegd (sectie 17).
- BEWUST NIET overnemen uit Zkr toegevoegd (sectie 18).
- Openstaand punt src/db/downloads.py vervallen (weg).
- Exception-lek deels opgelost (Spotweb-kant).

GEBRUIK
-------
Dit document is de zelfstandige, actuele overdracht van het Pulsarr-project.
Gebruik het als technische context voor verdere ontwikkeling. Ga ervan uit
dat onderstaande keuzes bewust zijn gemaakt. Verander bestaande architectuur
of functionaliteit niet zonder expliciete opdracht.

Bij twijfel: eerst de daadwerkelijke code lezen, niet aannemen.


==================================================
1. DOEL VAN DE PULSARR APP
==================================================

Pulsarr is een self-hosted webapp voor het beheren van een boeken-
verzameling. De app heeft twee gescheiden werelden:

1. LIBRARY (master)
   - Gesynchroniseerd vanuit Calibre (OPDS).
   - Bevat beschikbare boeken, covers, metadata (titel, auteur, serie,
     rating, beschrijving, uploaddatum) en lokale bestandspaden.
   - Bedoeld als "wat heb ik al".

2. WISHLIST (verlanglijst)
   - Door de gebruiker ingevoerde boeken die hij nog zoekt.
   - Wordt gekoppeld aan een geautomatiseerde Spotweb-zoekopdracht.
   - Vindt mogelijk matches (losse spots of boekenpakketten).
   - Resultaten komen in "Result Management", waar de gebruiker ze kan
     downloaden via SABnzbd.

Daarnaast:
- Activity Log: fouten en voortgang.
- Configuration: beheer van Calibre-, Spotweb- en SABnzbd-koppelingen,
  achtergrondintervallen en package-zoekwoorden.
- Achtergrondprocessen: periodiek automatisch zoeken + downloadstatus volgen.

Externe koppelingen:
- Spotweb      → bron van NZB-zoekresultaten (categorie 7020 = boeken)
- SABnzbd      → downloadclient
- Calibre      → master-bibliotheek via OPDS
- Cloudflare   → toegangscontrole (zie sectie 4)


==================================================
2. TECHNISCHE STACK
==================================================

FRONTEND
--------
- Jinja2 server-side templates
- Bootstrap 5.3.7 (CSS + JS bundle) via CDN
- Bootstrap Icons 1.11.3 via CDN
- Eigen CSS-laag: app/static/css/pulsarr.css
- Kleine inline <script>-blokken per template (geen bundler, geen SPA)

De UI is géén SPA. Filters, sortering en paginatie zijn grotendeels
server-side; detailmodals en sommige filters zijn client-side.

BACKEND
-------
- Python 3.14 (Docker base image: python:3.14-slim)
- FastAPI (webframework)
- Pydantic (config-validatie)
- SQLModel + SQLite (database)
- Jinja2 (templates)
- Requests (HTTP naar externe API's)
- PyJWT + cryptography (Cloudflare Access JWT-validatie, RS256)
- Pillow (cover-thumbnails)
- python-multipart (FastAPI Form())

Zie requirements.txt. Dependencies zijn op dit moment NIET gepind
(openstaand punt, zie sectie 15).

ARCHITECTUURPRINCIPE
--------------------
- Routers (app/screens/*_routes.py): HTTP/UI/forms/redirects.
  Geen business- of database-logica.
- Services (app/services/): business logic, database-interactie,
  externe API's.
- Models (app/models/): SQLModel-tabellen en platte dataclasses.
- Config (app/config/): persistent in config/config.json.
- Background (app/services/background_service.py): asyncio-workers.
- Templates (app/screens/*.html + _layout.html): server-side rendering.

LET OP: In de praktijk wijkt een aantal routers af van dit principe
(directe DB-queries in activity_log_routes.py, library_routes.py,
wishlist_routes.py). Bewust zo gelaten. Zie sectie 15.


==================================================
3. ARCHITECTUUR
==================================================

Globale flow:

Browser
   ↓  (Cloudflare Access JWT of LAN-bypass)
FastAPI app/main.py
   ↓  Depends(validate_cloudflare)
Router (app/screens/<naam>_routes.py)
   ↓
Service (app/services/<naam>_service.py)
   ↓
SQLModel / SQLite
   ↓
Externe services:
   - Spotweb
   - SABnzbd
   - Calibre

Screens-patroon (Zkr-conventie):
- Eén scherm = één router + één template, naast elkaar in app/screens/.
- Router: <naam>_routes.py
- Template: <naam>.html
- Gedeelde layout: app/screens/_layout.html
- Gedeelde Jinja2Templates: app/templates.py

Dit voorkomt naamconflicten (routers/settings.py vs config/settings.py)
en maakt "welke template hoort bij welke route" expliciet.

Services en verantwoordelijkheden:
- wishlist_service.py         → wishlist CRUD + zoeklogica
- bookmatch_service.py        → matching-helpers (geen DB)
- spotweb_service.py          → Spotweb API-client
- sabnzbd_service.py          → SABnzbd API-client
- calibre_service.py          → Calibre OPDS-client
- library_service.py          → sync Calibre ↔ Library-tabel
- library_storage_service.py  → covers downloaden en verkleinen
- downloads_service.py        → result-management + downloadstatus
- background_service.py       → periodieke workers
- activity_log_service.py     → logging-centralisatie


==================================================
4. SECURITY
==================================================

4.1 TOEGANGSMODEL
-----------------
Bestand: app/cloudflare.py
Koppeling: alle routers in app/main.py krijgen
`dependencies=[Depends(validate_cloudflare)]`.

Twee toegangspaden:

A. Via Cloudflare Access (mTLS + Access)
   - cloudflared voegt CF-* headers toe.
   - De CF_Authorization JWT (cookie of Cf-Access-Jwt-Assertion header)
     wordt gevalideerd tegen Cloudflare's publieke RSA-sleutels.
   - Sleutels worden opgehaald via /cdn-cgi/access/certs en 1 uur
     gecached.
   - Audience-claim wordt gecontroleerd (CF_ACCESS_AUD).

B. Via LAN-bypass
   - Geen CF-* headers aanwezig.
   - Bron-IP valt in een private range (10/8, 172.16/12, 192.168/16,
     127/8, ::1, fc00::/7, fe80::/10).
   - Request wordt toegestaan zonder JWT.

Fail-safe: publiek IP zonder CF-headers → JWT verplicht.
Dev-modus: CF_ACCESS_DISABLED=1 → auth volledig uit.

Configuratie via env vars:
  CF_ACCESS_TEAM_DOMAIN   (placeholder default)
  CF_ACCESS_AUD           (placeholder default)
  CF_ACCESS_DISABLED      (default "0" → auth AAN)

Bewust geaccepteerde risico's (zie module-docstring):
- Iedereen op het LAN kan Pulsarr zonder login gebruiken.
- CF-header-detectie is de ENIGE scheiding tussen "via Cloudflare" en
  "LAN". Als cloudflared CF-headers niet doorgeeft, valt CF-verkeer
  terug op LAN-bypass (bron-IP = 127.0.0.1).

4.2 ERROR-SANITIZATION (nieuw in v04)
--------------------------------------
Bestand: app/services/spotweb_service.py

_safe_error_message(exc):
- Strip't volledige URL's uit exception-strings (regex `https?://\S+`
  → `<url>`).
- Reden: requests-exceptions bevatten de request-URL inclusief
  ?apikey=... . Zonder sanitizing zou de key in de activity log en de
  config-UI kunnen belanden.
- Gebruikt in test_connection, fetch_recent_books, search_books,
  get_details.

_parse_xml_response(response, context):
- Detecteert HTML-respons (Content-Type of body-start).
- Geeft een duidelijke ValueError: "Spotweb returned HTML instead of
  XML (context). Check Spotweb URL and API key under Configuration."
- Vervangt de verwarrende "junk after document element"-fout.
- Gebruikt in alle vier de API-calls.

Status van het API-key-lek:
- Spotweb-kant: OPGELOST (via _safe_error_message + _parse_xml_response).
- SABnzbd-kant: NOG OPEN. sabnzbd_service.py gebruikt nog steeds
  `return False, str(exc)` in test_connection, add_url en
  get_download_status. Te fixen in de security-fase (sectie 17).

4.3 OPENSTAANDE SECURITY-PUNTEN
--------------------------------
Zie sectie 15 voor de volledige lijst. De belangrijkste:

1. SABnzbd exception-lek (analoog aan Spotweb-fix).
2. API-keys in config-HTML (value-attribuut).
3. CDN zonder SRI.
4. Destructieve acties zonder tweede bevestiging (sync_calibre,
   bulk-download).
5. Geen CSRF op POST-routes.
6. Geen pad-whitelist in /library/cover/{book_id}.
7. Geen security headers (CSP, X-Frame-Options, etc.).
8. Geen iss-claim-validatie in CF JWT-check.
9. Docker draait als root.
10. .env niet in .gitignore.
11. Geen rate limiting.

4.4 WAT GOED STAAT
------------------
- CF_ACCESS_DISABLED default "0" (auth AAN).
- .gitignore sluit config/config.json en config/*.db uit.
- .dockerignore sluit config/, data/, library/ uit.
- config_service.save() zet 0o600 op config.json (Unix only).
- Env-var overrides voor SPOTWEB_API_KEY en SABNZBD_API_KEY.
- Jinja2 auto-escape staat aan.
- Templates gebruiken textContent (niet innerHTML) in JS.
- encodeURIComponent op doorgegeven auteur.
- Server-side debounced search met parameterized ilike.
- Spotweb-foutmeldingen gesanitizeerd (v04).


==================================================
5. BESTANDSSTRUCTUUR
==================================================

app/
├── __init__.py
├── main.py
├── cloudflare.py
├── templates.py                          # gedeelde Jinja2Templates
├── config/
│   ├── __init__.py
│   ├── config_service.py
│   └── settings.py
├── db/
│   ├── __init__.py
│   └── database.py
├── models/
│   ├── __init__.py
│   ├── activity_log.py
│   ├── book.py
│   ├── enums.py
│   ├── library.py
│   ├── search_result.py
│   ├── search_result_record.py
│   └── spotweb_result.py
├── screens/
│   ├── __init__.py
│   ├── _layout.html                     # base layout
│   ├── activity_log.html
│   ├── activity_log_routes.py
│   ├── configuration.html
│   ├── configuration_routes.py
│   ├── library.html
│   ├── library_routes.py
│   ├── result_management.html
│   ├── result_management_routes.py
│   ├── wishlist.html
│   ├── wishlist_form.html
│   └── wishlist_routes.py
├── services/
│   ├── __init__.py
│   ├── activity_log_service.py
│   ├── background_service.py
│   ├── bookmatch_service.py
│   ├── calibre_service.py
│   ├── downloads_service.py
│   ├── library_service.py
│   ├── library_storage_service.py
│   ├── sabnzbd_service.py
│   ├── spotweb_service.py
│   └── wishlist_service.py
└── static/
    ├── css/pulsarr.css
    └── img/logo.svg

Project-root:
- dockerfile                              # COPY app, uvicorn app.main:app
- .dockerignore
- .gitignore
- requirements.txt
- test_*.py                               # dev-scripts (zie sectie 15)


==================================================
6. CONFIGURATIE
==================================================

Bron van waarheid: config/config.json
Map configureerbaar via PULSARR_CONFIG_DIR (default "config/").
Library en downloads configureerbaar via StorageSettings +
PULSARR_LIBRARY_ROOT.

ConfigService:
- load(): leest config.json → AppSettings; env-var overrides voor
  SPOTWEB_API_KEY en SABNZBD_API_KEY (Docker secrets).
- save(): schrijft AppSettings.model_dump() als JSON, 0o600 rechten.

AppSettings (Pydantic):
- spotweb     : url, api_key
- sabnzbd     : url, api_key, category (default "books")
- calibre     : url
- background  : download_status_interval (>=15s),
                wishlist_search_interval (>=300s)
- wishlist    : description_search_keywords (default
                "pakket, boekenpakket")
- storage     : library_dir ("Library"), downloads_dir ("Downloads"),
                root_dir (".")

Geen database-migratie nodig bij uitbreiding — Pydantic valt terug op
defaults voor ontbrekende velden.

UI (/configuration) biedt per sectie een Save- en Test-knop, plus
"Sync Library" voor Calibre. Alle knoppen POSTen naar één endpoint met
een `action`-discriminator: save_calibre, save_spotweb, test_spotweb,
save_sabnzbd, test_sabnzbd, save_background, save_wishlist,
test_calibre, sync_calibre.


==================================================
7. DATABASE
==================================================

SQLite in config/pulsarr.db.
DATABASE_URL = f"sqlite:///{DATABASE_FILE}" in app/db/database.py.
create_db_and_tables() draait in de FastAPI lifespan.

Tabellen:

activity_log
- id, created_at (aware UTC), level, source, message, details

books (wishlist)
- id, title, author, status (Status enum, default UNAVAILABLE)

library (Calibre master)
- id, calibre_id (unique, indexed), title, author, series, series_index,
  description, rating, uploaded_at, cover_url, epub_url, epub_size,
  epub_mtime, local_cover_path, local_epub_path

search_results (SearchResultRecord)
- id, book_id (indexed, GEEN FK), search_title, search_author,
  guid (indexed, niet uniek), description, download_url, size, age,
  category, search_type (SearchType enum), download_status
  (DownloadStatus enum), sabnzbd_id (indexed)

Belangrijk:
- GUID-deduplicatie gebeurt in de service-laag, niet in de DB.
- book_id = NULL voor title/author zoekresultaten.
- book_id gevuld voor full-search resultaten.


==================================================
8. EXTERNE INTEGRATIES
==================================================

8.1 SPOTWEB
------------
Bestand: app/services/spotweb_service.py
Categorie: 7020 (boeken).
API-endpoint: <configured URL>/api
Authenticatie: apikey in query-params.

_get_api_url() bevat een guard: lege URL → duidelijke ValueError.
DEZE GUARD MOET BLIJVEN.

Operaties:
- t=search met q=<query> (of zonder q voor recent)
- t=details met id=<guid>

Parsing: RSS/XML → SpotwebResult dataclasses, via _parse_xml_response
(HTML-detectie).

Foutafhandeling:
- _safe_error_message strip't URL's uit exceptions.
- _parse_xml_response geeft duidelijke fout bij HTML-respons.
- Activity log krijgt gesanitizeerde meldingen.

8.2 SABNZBD
-----------
Bestand: app/services/sabnzbd_service.py
API-endpoint: <configured URL>/api
Authenticatie: apikey in query-params.

Operaties:
- mode=version   → test_connection
- mode=addurl    → add_url (name = download_url)
- mode=queue     → get_download_status (eerste check)
- mode=history   → get_download_status (fallback) /
                   get_download_history

Queue-statussen: elke niet-failure → DownloadStatus.DOWNLOADING.
History-statussen:
  "Extracting"       → DOWNLOADING
  "Completed"        → DOWNLOADED
  "Failed"/"Failed/Retry" → DOWNLOAD_FAILED + fail_message
  anders             → onbekend (False + status-string)

LET OP: gebruikt nog `return False, str(exc)` (analoog aan Spotweb
vóór v04). Fix in security-fase (sectie 17).

8.3 CALIBRE
-----------
Bestand: app/services/calibre_service.py
Endpoint: <configured URL>/opds?library_id=04.Calibre
LET OP: library_id=04.Calibre is HARDCODED. Kandidaat voor
configuratie-uitbreiding (vergelijkbaar met de Spotweb-URL destijds).

Flow:
1. GET op OPDS-root, zoek de entry "By Newest".
2. Volg de feed, pagina voor pagina via rel="next".
3. Per entry: titel, auteur, calibre_id, description (HTML gestript),
   rating (uit RATING: ★★★), series (uit SERIES: naam [index]),
   uploaded_at, cover_url, epub_url + size + mtime.
4. library_service.sync() schrijft dit naar de library-tabel.

Sync-gedrag:
- Nieuwe calibre_id → insert.
- Bestaande calibre_id → update.
- calibre_id die niet meer in Calibre bestaat → session.delete
  (DESTRUCTIEF).
- Cover wordt gedownload via library_storage_service.download_cover()
  als local_cover_path leeg is; thumbnail max 300x450, JPEG q=85.


==================================================
9. ZOEKLOGICA (WISHLIST)
==================================================

Bestand: app/services/wishlist_service.py

Vier modi:

A. FULL SEARCH (search_book_full)
1. Directe title-search via spotweb_service.search_books(book.title).
2. Directe author-search via spotweb_service.search_books(book.author).
3. Combineren op guid (dict).
4. Per resultaat: book_matches(title, author, spot_title, "").
5. Als GEEN directe match: package search als fallback.
   - Keywords uit settings.wishlist.description_search_keywords.
   - Per keyword: search_books(keyword), per resultaat get_details.
   - Match via book_matches(..., details.description).
6. Nieuwe records met book_id=book.id, search_type=BOOK.
7. book.status = POSSIBLE_MATCH als er matches zijn.
8. Deduplicatie: op (book_id, guid, search_type).

B. TITLE SEARCH (search_book, search_type="title")
1. search_books(book.title).
2. Package search met search_type="title" (per regel
   match_title_or_author).
3. Records met book_id=NULL, search_type=TITLE.
4. book.status wordt NIET gewijzigd.

C. AUTHOR SEARCH (search_book, search_type="author")
Idem als B, met book.author, search_type=AUTHOR, book_id=NULL.

D. BACKGROUND SEARCH (search_books, door BackgroundService)
1. Boeken met status UNAVAILABLE ophalen.
2. fetch_recent_books_paginated(pages=3, page_size=100) = 300 recente
   releases.
3. Per boek, per resultaat:
   a. book_matches(book.title, book.author, spot_title, "")
      → direct match.
   b. Als geen match: check of de Spot-titel een package-keyword bevat
      (uit description_search_keywords). Zo nee → skip.
   c. Zo ja: get_details(guid), dan book_matches(..., description).
4. Nieuwe records met book_id=book.id, search_type=BOOK.
5. book.status = POSSIBLE_MATCH als er matches zijn.

Efficiency-detail:
In background search wordt get_details NIET voor ieder resultaat
opgehaald. Alleen als de Spot-titel een package-keyword bevat.
Voorkomt onnodige detail-requests.

| Modus              | Spotweb API             | Lokale verwerking          |
| ------------------ | ----------------------- | -------------------------- |
| A Full Search      | volledige index         | package descriptions       |
| B Title Search     | volledige index         | package descriptions       |
| C Author Search    | volledige index         | package descriptions       |
| D Background       | recente 300             | normale spots + packages   |


==================================================
10. BOOK MATCHING
==================================================

Bestand: app/services/bookmatch_service.py

_normalize():
- Unicode NFKD → ASCII
- lowercase
- niet-alfanumeriek → spatie
- whitespace-collapse

_author_variants():
- "Voornaam Achternaam" ↔ "Achternaam Voornaam"
- Bij één woord: enkele variant.

_contains_title_and_author(text, title, author):
- Genormaliseerde titel moet in genormaliseerde tekst zitten EN
- één van de auteur-varianten moet erin zitten.

match_spot_title / match_package_description / book_matches:
- book_matches combineert titel-match + package-description-match.
- match_package_description splitst op <br\s*/?> én \r?\n en checkt
  per regel (voorkomt valse matches over regels heen).

match_title_or_author(text):
- Checkt titel OF auteur in de (genormaliseerde) tekst.
- Bedoeld voor TITLE/AUTHOR package-fallback (per regel).

BELANGRIJK: Deze functies zijn de kern van de package-detectie. Niet
zonder expliciete opdracht aanpassen.


==================================================
11. ACHTERGRONDPROCESSEN
==================================================

Bestand: app/services/background_service.py

BackgroundService start in FastAPI lifespan:
- download_status_worker
- wishlist_search_worker

download_status_worker:
- Loop: lees settings.background.download_status_interval (>=15s).
- Slaap interval, dan alle SearchResultRecord met
  download_status=DOWNLOADING checken via downloads_service.
- check_download_status() werkt book.status bij.

wishlist_search_worker:
- Eerste iteratie direct (geen wachttijd), daarna interval
  (settings.background.wishlist_search_interval, >=300s).
- Roept wishlist_service.search_books(session) aan.
- Logt "Automatic Search Completed" via log_background_task().
- Bij fout: "Automatic Search Failed".

manual_wishlist_search():
- Getriggerd door /wishlist/search (POST).
- Dedupliceert: als er al een manual task loopt, doet hij niets.
- Gebruikt asyncio.Lock zodat manual en automatic search niet
  tegelijk lopen.

Blocking werk (Spotweb-calls, SQLModel) draait via asyncio.to_thread
zodat de event loop vrij blijft.

ActivityLogService.log_background_task():
- Dedupliceert "Automatic Search Completed": werkt bestaande regel bij
  in plaats van nieuwe aan te maken. Voorkomt onbeperkte groei.


==================================================
12. UI / UX
==================================================

Base layout: app/screens/_layout.html
- Sidebar-navigatie (Library / Wishlist / Result Management /
  Activity Log / Configuration).
- Mobile menu met off-canvas sidebar.
- Versie-footer met "v0.8.9" (hardcoded — zie sectie 15).
- Bootstrap CSS/JS via CDN (zie sectie 4.3 punt 3).

Pagina-specifiek:

Library (/library)
- Grid met covers, sorteren op upload-datum / titel / auteur,
  rating-filter, zoekfilter (server-side, debounced 400ms),
  paginatie, modal met boekdetails.
- Server-side filtering/sortering via SORT_COLUMNS-dict in router.

Wishlist (/)
- Tile-grid, statusbadge, live client-side filter.
- Per boek een actiemenu (drie zoekmodi, edit, delete, add-by-author).
- Actiemenu staat BUITEN de scroll-container (om clipping te voorkomen).
- Delete met bevestigingsmodal.

Wishlist form (/wishlist/add_book, /wishlist/{id}/edit)
- Titel, auteur, status.

Result Management (/result-management)
- Tile-grid van SearchResultRecord.
- Statusbadge, size (MB), selectie-checkboxen.
- Bulk-download (direct) en bulk-delete (met modal).
- Client-side zoekfilter.
- Modal voor volledige Spot-titel.
- Weergave-label hangt af van search_type:
  TITLE  → search_title
  AUTHOR → search_author
  BOOK   → "author - title" (of één van beide)

Activity Log (/activity-log)
- Tabel met datum, level, source, message, details.
- Client-side zoekfilter.
- Clear-log met bevestigingsmodal (POST /activity-log/clear).

Configuration (/configuration)
- Vijf secties (Calibre, Spotweb, SABnzbd, Background, Wishlist).
- Eén groot formulier met action-discriminator.
- Test-connection messages als alerts.
- Book-count indicator na Calibre-sync.

Stijl:
- Bootstrap 5.3.7 + Bootstrap Icons.
- Eigen CSS-laag in app/static/css/pulsarr.css.
- Gebruikt moderne CSS (:has()) — vereist Chromium 105+, Safari 15.4+,
  Firefox 121+.
- Geen dark mode (bewust niet aanwezig).
- Taalmix NL/EN in UI-teksten (cosmetisch).

Client-side vs server-side filtering (bewust niet uniform):
- Activity Log      → client-side
- Result Management → client-side
- Wishlist          → client-side
- Library           → server-side (debounced)

Modals gebruiken textContent (niet innerHTML) — bewust, want
beschrijvingen kunnen HTML bevatten. NIET wijzigen zonder
escaping-laag.


==================================================
13. DEPLOYMENT
==================================================

Dockerfile:
- Base: python:3.14-slim
- ENV: PULSARR_CONFIG_DIR=/config, PULSARR_LIBRARY_ROOT=/library
- COPY app ./app
- mkdir -p /config /library
- CMD: uvicorn app.main:app --host 0.0.0.0 --port 8010
- EXPOSE 8010

Aandachtspunten:
- Container draait als root (geen USER-directive).
- Geen HEALTHCHECK.
- Geen multi-stage build.
- Base image python:3.14 is erg recent; controleer compatibiliteit
  met Pillow en SQLModel.
- workers=1 is impliciet. MOET zo blijven: de achtergrondtaken
  draaien in-process en SQLModel heeft geen cross-process locking.
  Voeg GEEN --workers N toe.

.dockerignore sluit config/, data/, library/, *.db, *.sqbpro uit.
Let op: *.sqbpro lijkt een typefout; controleer.

.gitignore sluit config/config.json en config/*.db uit.
LET OP: .env-bestanden zijn NIET expliciet ignored.

GitHub Actions: .github/workflows/docker.yml
- Trigger: push tags v*
- Permissions: contents:read, packages:write
- Image: ghcr.io/robwiesener/pulsarr
- Platforms: linux/amd64, linux/arm64
- Build via Buildx.
- Actions: checkout@v6, setup-buildx-action@v3, login-action@v4,
  metadata-action@v6, build-push-action@v7.


==================================================
14. RELEASEPROCES
==================================================

1. Code wijzigen.
2. git diff --check
3. python -m compileall -q app
4. Handmatige functionele tests.
5. git diff controleren.
6. Committen.
7. Versie bijwerken:
   - app/screens/_layout.html (sidebar-footer)
   - eventueel andere plekken
8. Tag maken/verplaatsen indien nodig.
9. main pushen.
10. Version-tag pushen → GitHub Actions bouwt image naar GHCR.

Bij bestaande remote tag: `git push --force origin <tag>` kan andere
consumers breken. Voorzichtig.

Werkwijze (naar Zkr-conventie):
- Altijd committen vóór een nieuwe wijziging.
- Eén stap per keer, testen, dan pas verder.
- Commit-berichten in het Engels.
- OVERDRACHT.md wordt meegecommit bij elke wijziging.


==================================================
15. OPENSTAANDE PUNTEN
==================================================

SECURITY (zie ook sectie 4.3)
------------------------------
1. SABnzbd exception-lek (analoog aan Spotweb-fix).
2. API-keys in config-HTML (value-attribuut).
3. CDN zonder SRI (Bootstrap, Bootstrap Icons).
4. Destructieve acties zonder tweede bevestiging (sync_calibre,
   bulk-download).
5. Geen CSRF op POST-routes.
6. Geen pad-whitelist in /library/cover/{book_id}.
7. Geen security headers (CSP, X-Frame-Options, etc.).
8. Geen iss-claim-validatie in CF JWT-check.
9. Docker draait als root.
10. .env niet in .gitignore.
11. Geen rate limiting.

ARCHITECTUUR / ROBUUSTHEID
---------------------------
12. test_prowlarr.py importeert niet-bestaande
    app.services.prowlarr_service.
13. test_spotweb_rss.py heeft hardcoded IP (192.168.1.30).
14. test_spotweb_download.py heeft hardcoded RECORD_ID = 4.
15. Routers schenden op enkele plekken de "geen DB in router"-regel
    (activity_log_routes.py, library_routes.py, wishlist_routes.py).
16. Status[status] (Enum-lookup met string) → KeyError → 500 bij
    ongeldige input. Geen nette 400.
17. SpotwebService._log() opent zijn eigen Session(engine) i.p.v.
    session van caller.
18. library_storage_service.py leest config in __init__ op
    import-tijd (wijzigingen in storage.root_dir pas effectief na
    restart).
19. library_id=04.Calibre is hardcoded in calibre_service.
20. download_status_worker gebruikt sleep als eerste actie; eerste
    status-check pas na interval.
21. downloads_service.check_download_status() heeft inconsistent
    return-type (tuple vs None).
22. count_books() doet len(...all()) i.p.v. select(func.count()).

OPERATIONEEL
------------
23. Activity log kan snel vullen bij frequent manual search (INFO per
    zoekopdracht title/author).
24. Veel print()-statements in services i.p.v. activity_log_service.
25. requirements.txt is niet gepind.
26. Geen HEALTHCHECK in Dockerfile.
27. Versie "v0.8.9" hardcoded in _layout.html — verouderd t.o.v.
    code (huidige tag v0.9.7). Bumpen vóór volgende release.
28. max-scale=1.0 in viewport (a11y: pinch-zoom geblokkeerd).
29. Taalmix NL/EN in UI-teksten.
30. library_cover is de enige "cover"-route; epub-serving ontbreekt
    (epub_url en local_epub_path worden wel opgeslagen).

REST / KLEIN
------------
31. src/db/downloads.py (dode code) — VERLEDEN TIJD, verwijderd in
    v04.
32. selectAll-referentie in result_management.html bestaat niet in
    de template (dode JS).
33. library_storage_service: *.sqbpro in .dockerignore lijkt typefout.


==================================================
16. NIET ZOMAAR WIJZIGEN
==================================================

Gevoelig, niet zonder expliciete opdracht aanpassen:

- Cloudflare-validatie (app/cloudflare.py) en CF-headers-detectie.
- LAN-bypass-keuze (bewust ontwerp, bekende risico's).
- Spotweb endpoint-opbouw (_get_api_url guard).
- _safe_error_message en _parse_xml_response in spotweb_service.
- API-key handling in config_service (env-overrides).
- Package-fallback-logica (wishlist_service._search_package_matches).
- Book matching (bookmatch_service) — _normalize, _author_variants,
  match_title_or_author, book_matches.
- SearchResultRecord deduplicatie (per search_type verschillend).
- De bewuste keuze dat title/author searches book_id=NULL hebben en
  book.status niet wijzigen.
- SABnzbd-integratie en status-mapping.
- Calibre-integratie en sync-gedrag (inclusief destructieve delete).
- Achtergrondtaken (locks, to_thread, deduplicatie).
- Config.json-architectuur en env-var overrides.
- SQLite-schema.
- screens/<naam>_routes.py + <naam>.html patroon en app/templates.py.
- Docker-platforms, image-naam, tag-trigger (v*).
- Bestaande Bootstrap/Jinja2 UI-structuur.
- textContent (niet innerHTML) in modals.
- Jinja2 auto-escape niet uitzetten (|safe niet toevoegen).
- workers=1 in uvicorn (in-process background + SQLite).


==================================================
17. ROADMAP NAAR ZKR-ALIGNMENT
==================================================

Pulsarr wordt stapsgewijs in lijn gebracht met Zkr. Elke stap is
een aparte commit + OVERDRACHT-update.

STAP 1 — BESTANDSSTRUCTUUR ✅ VOLTOOID
--------------------------------------
- src/ → app/
- routers/ + templates/ → app/screens/ (plat)
- <naam>_routes.py + <naam>.html (Zkr-conventie)
- app/templates.py (gedeelde Jinja2Templates)
- dockerfile aangepast (COPY app, uvicorn app.main:app)
- src/db/downloads.py verwijderd

STAP 2 — KLEINE BUGS ✅ DEELS VOLTOOID
---------------------------------------
- Spotweb HTML-detectie + error-sanitization (v04) ✅
- SABnzbd error-sanitization (analoog) ⏳
- selectAll dode JS opruimen ⏳
- test_prowlarr.py fixen (prowlarr_service bestaat niet) ⏳
- test_spotweb_rss.py hardcoded IP → env-var ⏳

STAP 3 — SECURITY (in één sessie)
---------------------------------
a. CSRF double-submit cookie (middleware + tokens in alle
   POST-forms, naar Zkr-model: csrf.py + csrf_middleware.py).
b. Rate limiting per IP (SlowAPI, buitenste laag, vóór CSRF).
c. Generieke exception handler (geen str(exc) naar client).
d. API-key-masking in configuration.html (placeholder "********",
   bestaande waarde behouden bij lege submit).
e. SABnzbd _safe_error_message (analoog aan Spotweb).
f. safe_fs-achtige pad-validatie voor /library/cover en
   library_storage_service (is_under + symlink-check).
g. SQLite hardening: WAL, busy_timeout=30s, threading.RLock,
   transaction()-contextmanager.
h. Multi-worker guard in main.py (weiger te starten als
   UVICORN_WORKERS > 1) + comment in Dockerfile.
i. Ruff CI (--select F, scope app/) in GitHub Actions.
j. Security headers middleware (CSP, X-Frame-Options,
   X-Content-Type-Options, Referrer-Policy).
k. SRI-hashes op CDN-links of Bootstrap vendoren in
   app/static/vendor/.

STAP 4 — OPERATIONELE VOLWASSENHEID
------------------------------------
a. app/version.py als single source of truth voor _layout.html.
b. Migraties als .sql-bestanden (pas bij eerste echte
   schema-wijziging; documenteer nu al het plan).
c. Transactie-discipline documenteren (failure-paths in
   transaction(), success-paths niet).
d. BEWUST-NIET-lijst uitbreiden op basis van praktijkervaring.

STAP 5 — STRUCTURELE KEUZES (alleen op verzoek)
-----------------------------------------------
a. Trash-systeem voor library-rijen (analoog aan Zkr).
b. error_code-kolommen op search_results.
c. packages-terminologie hernoemen om botsing met Zkr's
   packages-tabel te voorkomen (indien ooit code wordt
   overgenomen).

NIET DOEN (tenzij expliciet gevraagd):
- Htmx introduceren.
- PWA / iOS homescreen / manifest.json.
- Aparte proces-modules (Spotter/Matcher/Dispatcher/Monitor/
  Publisher/Housekeeper) — Pulsarr's scope rechtvaardigt dit niet.
- Migraties introduceren vóór de eerste echte schema-wijziging.
- Kodi-specifieke conventies.


==================================================
18. BEWUST NIET OVERNEMEN UIT ZKR
==================================================

Deze keuzes zijn gemaakt en hoeven niet opnieuw ter discussie:

- Geen htmx. Inline JS per template volstaat voor Pulsarr's scope.
- Geen SPA / React / Vue.
- Geen PWA / manifest.json / iOS homescreen.
- Geen aparte proces-modules. background_service.py met twee
  workers is proportioneel.
- Geen migratie-runner tot de eerste echte schema-wijziging.
- Geen trash voor wishlist-rijen (klein, herstelbaar via UI).
- Geen paginatie op wishlist (klein aantal boeken).
- Geen multi-worker uvicorn (in-process background + SQLite).
- Geen error_code-kolommen op search_results (nu).
- Geen rate limits aanpassen aan Zkr-niveau (Pulsarr is LAN-tool).
- Geen screens-submappen (plat is voldoende voor 6 schermen).
- Geen _helpers.py / _toggles.py in screens/ (pas bij noodzaak).


==================================================
19. VALIDATIE BIJ WIJZIGINGEN
==================================================

Standaard:
  git diff --check
  python -m compileall -q app

Handmatig testen:
- relevante zoekmodus (full / title / author / background)
- config-pagina (save + test per sectie)
- library-sync (indien geraakt)
- result management (download + delete)
- activity log (indien logging geraakt)
- Cloudflare-validatie:
   * LAN-toegang zonder CF-headers moet werken.
   * CF-headers zonder geldige JWT moet 400/401 geven.
   * CF_ACCESS_DISABLED=1 moet alles doorlaten.

Lokaal starten:
  cd /Volumes/Data/01.Temp/pulsarr
  source .venv/bin/activate
  export PULSARR_CONFIG_DIR=config
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8010

Controle na rename/refactor:
  grep -rn "from src\.\|import src\." app/ && echo "FOUT" || echo "OK"
  ls src 2>/dev/null && echo "FOUT" || echo "OK"


==================================================
20. DOEL VOOR DE NIEUWE CHAT
==================================================

De nieuwe ChatGPT-chat moet dit document behandelen als de actuele
technische context van Pulsarr.

De gebruiker wil de app verder ontwikkelen vanuit de bestaande codebase,
zonder bestaande functionaliteit onnodig te herschrijven, en stapsgewijs
in lijn brengen met Zkr (sectie 17).

Bij twijfel:
- eerst de daadwerkelijke bestanden/code laten bekijken;
- niet aannemen dat een functie anders werkt dan hierboven beschreven;
- geen grote refactor voorstellen als een kleine wijziging voldoende is;
- geen versie verhogen tenzij de gebruiker dat expliciet wil;
- geen nieuwe database-migratie introduceren tenzij technisch
  noodzakelijk;
- bestaande release- en Docker-workflow respecteren;
- security-bevindingen uit sectie 4.3 en 15 niet stilzwijgend negeren:
  als een wijziging raakt aan logging, exceptions, config-UI,
  CDN-loading of POST-routes, de betreffende punten expliciet benoemen;
- bij elke wijziging OVERDRACHT.md bijwerken en meecommitten
  (Zkr-werkwijze).
