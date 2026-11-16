PULSARR — PROJECTOVERDRACHT v03
(vervangt v02; opgesteld na volledige code-inventarisatie)


==================================================
0. GEBRUIK VAN DIT DOCUMENT
==================================================

Dit document is de zelfstandige, actuele overdracht van het Pulsarr-project.

Gebruik het als technische context voor verdere ontwikkeling. Ga ervan uit
dat onderstaande keuzes bewust zijn gemaakt. Verander bestaande architectuur
of functionaliteit niet zonder expliciete opdracht.

Belangrijkste wijzigingen t.o.v. v02 staan in sectie 17 (Delta).
Alle openstaande verbeterpunten staan gebundeld in sectie 15.


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
- Eigen CSS-laag: src/static/css/pulsarr.css
- Kleine inline <script>-blokken per template (geen bundler, geen SPA)

BELANGRIJK: De UI is géén SPA. Filters, sortering en paginatie zijn
grotendeels server-side; detailmodals en sommige filters zijn client-side.
Per pagina verschilt dit (zie sectie 12).

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

Zie requirements.txt. Op dit moment zijn dependencies NIET gepind
(openstaand punt, zie sectie 15).

ARCHITECTUURPRINCIPE
--------------------
- Routers: HTTP/UI/forms/redirects. Geen business- of database-logica.
- Services: business logic, database-interactie, externe API's.
- Models: SQLModel-tabellen en platte dataclasses.
- Config: persistent in config/config.json.
- Background: asyncio-workers in BackgroundService.

LET OP: In de praktijk wijkt een aantal routers af van dit principe
(directe DB-queries in activity_log.py, library.py, wishlist.py).
Dit is bewust zo gelaten; zie sectie 17 (Delta) en 15 (openstaand).


==================================================
3. ARCHITECTUUR
==================================================

Globale flow:

Browser
   ↓  (Cloudflare Access JWT of LAN-bypass)
FastAPI main.py
   ↓  Depends(validate_cloudflare)
Router
   ↓
Service
   ↓
SQLModel / SQLite
   ↓
Externe services:
   - Spotweb
   - SABnzbd
   - Calibre

Services en verantwoordelijkheden:

wishlist_service.py         → wishlist CRUD + zoeklogica (book/title/author)
bookmatch_service.py        → matching-helpers (geen DB)
spotweb_service.py          → Spotweb API-client
sabnzbd_service.py          → SABnzbd API-client
calibre_service.py          → Calibre OPDS-client
library_service.py          → sync tussen Calibre en Library-tabel
library_storage_service.py  → covers downloaden en verkleinen
downloads_service.py        → result-management acties + downloadstatus
background_service.py       → periodieke workers
activity_log_service.py     → logging-centralisatie


==================================================
4. SECURITY (nieuw t.o.v. v02)
==================================================

Dit is de grootste wijziging sinds v02. Lees deze sectie aandachtig voordat
je routes, configuratie of logging aanpast.

4.1 TOEGANGSMODEL
-----------------
Bestand: src/cloudflare.py
Koppeling: alle routers in src/main.py krijgen `dependencies=[Depends(validate_cloudflare)]`.

Twee toegangspaden:

A. Via Cloudflare Access (mTLS + Access)
   - cloudflared voegt CF-* headers toe.
   - De CF_Authorization JWT (cookie of Cf-Access-Jwt-Assertion header)
     wordt gevalideerd tegen Cloudflare's publieke RSA-sleutels.
   - Sleutels worden opgehaald via /cdn-cgi/access/certs en 1 uur gecached.
   - Audience-claim wordt gecontroleerd (CF_ACCESS_AUD).

B. Via LAN-bypass
   - Geen CF-* headers aanwezig.
   - Bron-IP valt in een private range (10/8, 172.16/12, 192.168/16,
     127/8, ::1, fc00::/7, fe80::/10).
   - Request wordt toegestaan zonder JWT.

Fail-safe: publiek IP zonder CF-headers → JWT verplicht.

Dev-modus: CF_ACCESS_DISABLED=1 → auth volledig uit.

Configuratie via env vars:
  CF_ACCESS_TEAM_DOMAIN   (default: placeholder "https://<jouw-team>.cloudflareaccess.com")
  CF_ACCESS_AUD           (default: placeholder "<jouw-aud-tag>")
  CF_ACCESS_DISABLED      (default: "0" → auth AAN)

Bewust geaccepteerde risico's (staan ook in de module-docstring):
- Iedereen op het LAN kan Pulsarr zonder login gebruiken. Dit is bewust.
- De CF-header-detectie is de ENIGE scheiding tussen "via Cloudflare" en
  "LAN". Als cloudflared om wat voor reden dan ook CF-headers niet
  doorgeeft (verkeerde config, proxy-rewrite, etc.), valt CF-verkeer
  terug op LAN-bypass (bron-IP is dan 127.0.0.1). Dit is een reëel
  operationeel risico dat de beheerder moet kennen.

Niet aanwezig (bewust of openstaand):
- Geen `iss`-claim-validatie (alleen audience + signature).
- Geen CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
- Geen CSRF-tokens op POST-routes.
- Geen rate limiting.
- Geen sessie-cookie of logout (CF regelt dit buiten de app).

4.2 BEKENDE LEKPUNTEN IN DE HUIDIGE CODE
----------------------------------------
Deze zijn nog NIET opgelost. Ze staan hier zodat een nieuwe chat ze niet
opnieuw hoeft te ontdekken.

1. API-key-lek via exception-strings (HOOG)
   - sabnzbd_service.test_connection()  → return False, str(exc)
   - sabnzbd_service.add_url()          → str(exc) gelogd én geretourneerd
   - spotweb_service.test_connection()  → return False, str(exc)
   - spotweb_service._log(..., details=str(exc))
   - wishlist_service._log(..., details=f"...query={query!r}: {exc}")

   Requests-exceptions bevatten doorgaans de volledige request-URL,
   inclusief ?apikey=...

   Deze strings belanden in:
   - de config-UI (alert-blokken)
   - de activity log (/activity-log, kolom Details + data-search)
   - de DOM (data-attributen)

   Mitigatie die in het document wordt voorgesteld (niet nu uitvoeren):
   een helper die vóór logging/return de URL uit de exception strip't.

2. API-keys in de config-HTML (HOOG)
   - configuration/index.html: value="{{ settings.spotweb.api_key }}"
     en value="{{ settings.sabnzbd.api_key }}".
   - type="password" maskeert alleen visueel.
   - Aanbevolen patroon: placeholder "********" tonen en bij lege submit
     de bestaande waarde behouden.

3. CDN-loading zonder Subresource Integrity (MIDDEL)
   - Bootstrap CSS/JS en Bootstrap Icons worden via jsDelivr geladen
     zonder integrity="sha384-..." en zonder crossorigin.
   - Als jsDelivr gecompromitteerd raakt, draait er vreemde JS in de
     context van Pulsarr — met toegang tot alle API keys in de DOM.
   - Privacy: elke page load doet een request naar jsDelivr.
   - Aanbevolen: SRI-hashes toevoegen OF Bootstrap vendoren in
     src/static/vendor/.

4. Destructieve acties zonder extra bevestiging
   - /configuration "sync_calibre" verwijdert boeken die niet meer in
     Calibre staan (library_service.sync doet session.delete voor alles
     wat niet meer in de Calibre-feed zit).
   - Eén verkeerde POST wist de library. Geen tweede bevestigingsstap.
   - /result-management/download start direct SABnzbd-jobs (geen modal).

5. Geen CSRF-bescherming op POST-routes
   - Alle POST-forms in alle templates.
   - Met CF Access + LAN-bypass is het risico beperkt tot LAN-gebruikers
     en tot CSRF vanaf een gecompromitteerde site die de gebruiker
     bezoekt terwijl hij op het LAN is.

6. pad-validatie /library/cover/{book_id}
   - Serveert local_cover_path uit de DB, alleen met is_file()-check.
   - Pad komt uit eigen sync, dus risico is beperkt, maar defense-in-depth
     (whitelist tegen library_dir) zou passen.

7. XML-parsing (ET.fromstring) op Calibre-OPDS en Spotweb-RSS
   - Python's ElementTree blokkeert external entities standaard, maar is
     vatbaar voor "billion laughs" / quadratic blowup.
   - Beide bronnen zijn vertrouwd in self-hosted context.
   - Dit is een BEWUST GEACCEPTEERD RISICO.

8. Test-scripts met hardcoded IP en dode imports
   - test_spotweb_rss.py: SPOTWEB_URL = "http://192.168.1.30:9080/api"
   - test_prowlarr.py: importeert src.services.prowlarr_service
     (bestaat niet meer in de huidige codebase)
   - test_spotweb_download.py: RECORD_ID = 4 (dev-script)
   - Niet productie-kritisch; opruimen vóór publicatie.

4.3 SECURITY-DEFAULTS DIE GOED STAAN
------------------------------------
- CF_ACCESS_DISABLED default is "0" (auth AAN).
- .gitignore sluit config/config.json en config/*.db uit.
- .dockerignore sluit config/, data/, library/ uit → geen secrets in image.
- config_service.save() zet 0o600 op config.json (Unix only).
- Env-var overrides voor SPOTWEB_API_KEY en SABNZBD_API_KEY (Docker secrets).
- Jinja2 auto-escape staat aan (FastAPI default); templates gebruiken
  textContent in JS, niet innerHTML.
- encodeURIComponent op doorgegeven auteur in wishlist "same author"-link.
- Search-while-typing in library is server-side met parameterized ilike
  (geen SQL injection).


==================================================
5. BESTANDSSTRUCTUUR
==================================================

src/
├── main.py
├── cloudflare.py                       # Cloudflare Access + LAN-bypass
├── config/
│   ├── config_service.py               # load/save config.json
│   └── settings.py                     # Pydantic modellen
├── db/
│   ├── database.py                     # engine + get_session
│   └── downloads.py                    # DODE CODE (zie sectie 15)
├── models/
│   ├── activity_log.py                 # ActivityLog tabel
│   ├── book.py                         # Book tabel (wishlist)
│   ├── enums.py                        # Status / SearchType / DownloadStatus
│   ├── library.py                      # Library tabel (Calibre master)
│   ├── search_result_record.py         # SearchResultRecord tabel
│   ├── search_result.py                # platte dataclass
│   └── spotweb_result.py               # platte dataclass
├── routers/
│   ├── activity_log.py
│   ├── library.py
│   ├── result_management.py
│   ├── settings.py
│   └── wishlist.py
├── services/
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
├── static/
│   ├── css/pulsarr.css
│   └── img/logo.svg
└── templates/
    ├── activity_log/index.html
    ├── configuration/index.html
    ├── library/index.html
    ├── pulsarr/index.html              # base layout
    ├── result_management/index.html
    └── wishlist/
        ├── index.html
        └── form.html

Overige bestanden (project-root):
- Dockerfile
- .dockerignore
- .gitignore
- requirements.txt
- test_*.py (dev-scripts, zie sectie 4.2 punt 8)


==================================================
6. CONFIGURATIE
==================================================

Bron van waarheid: config/config.json
Map configureerbaar via PULSARR_CONFIG_DIR (default "config/").
Pad naar library en downloads configureerbaar via StorageSettings +
PULSARR_LIBRARY_ROOT (zie library_storage_service.py).

ConfigService:
- load(): leest config.json → AppSettings; env-var overrides voor
  SPOTWEB_API_KEY en SABNZBD_API_KEY (Docker secrets).
- save(): schrijft AppSettings.model_dump() als JSON, 0o600 rechten.

AppSettings (Pydantic):
- spotweb        : url, api_key
- sabnzbd        : url, api_key, category (default "books")
- calibre        : url
- background     : download_status_interval (>=15s),
                   wishlist_search_interval (>=300s)
- wishlist       : description_search_keywords (default "pakket, boekenpakket")
- storage        : library_dir ("Library"), downloads_dir ("Downloads"),
                   root_dir (".")

Configuratie is persistent in config.json. Geen database-migratie nodig
bij uitbreiding — Pydantic valt terug op defaults voor ontbrekende velden.

De UI (/configuration) biedt per sectie een Save- en Test-knop, plus
"Sync Library" voor Calibre. Alle knoppen POSTen naar één endpoint met
een `action`-discriminator (save_calibre, save_spotweb, test_spotweb,
save_sabnzbd, test_sabnzbd, save_background, save_wishlist,
test_calibre, sync_calibre).


==================================================
7. DATABASE
==================================================

SQLite in config/pulsarr.db.
DATABASE_URL = f"sqlite:///{DATABASE_FILE}" in src/db/database.py.
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
- GUID-deduplicatie gebeurt in de service-laag (wishlist_service),
  niet in de DB (geen unique constraint).
- book_id = NULL voor title/author zoekresultaten (losse zoekopdrachten).
- book_id gevuld voor full-search resultaten (gekoppeld aan wishlist).


==================================================
8. EXTERNE INTEGRATIES
==================================================

8.1 SPOTWEB
------------
Bestand: src/services/spotweb_service.py
Categorie: 7020 (boeken).
API-endpoint: <configured URL>/api
Authenticatie: apikey in query-params.
URL en key configureerbaar via Configuration-pagina.

_get_api_url() bevat een guard: lege URL → duidelijke ValueError.
DEZE GUARD MOET BLIJVEN.

Operaties:
- t=search met q=<query> (of zonder q voor recent)
- t=details met id=<guid>

_get_api_url() voorbeeld:
  url = settings.spotweb.url.strip()
  if not url: raise ValueError("Spotweb URL is not configured...")
  return url.rstrip("/") + "/api"

Parsing: RSS/XML → SpotwebResult dataclasses.
Caching: geen (elke request doet HTTP).
Logging: fouten via _log(...) naar activity log (met eerder genoemd
lek-risico, zie sectie 4.2 punt 1).

8.2 SABNZBD
-----------
Bestand: src/services/sabnzbd_service.py
API-endpoint: <configured URL>/api
Authenticatie: apikey in query-params.

Operaties:
- mode=version         → test_connection
- mode=addurl          → add_url (name = download_url)
- mode=queue           → get_download_status (eerste check)
- mode=history         → get_download_status (fallback) / get_download_history

Queue-statussen (elke niet-failure) → DownloadStatus.DOWNLOADING.
History-statussen:
  "Extracting"       → DOWNLOADING
  "Completed"        → DOWNLOADED
  "Failed"/"Failed/Retry" → DOWNLOAD_FAILED + fail_message
  anders             → onbekend (False + status-string)

8.3 CALIBRE
-----------
Bestand: src/services/calibre_service.py
Endpoint: <configured URL>/opds?library_id=04.Calibre
LET OP: library_id=04.Calibre is HARDCODED. Dit is een kandidaat voor
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
- calibre_id die niet meer in Calibre bestaat → session.delete (DESTRUCTIEF).
- Cover wordt gedownload via library_storage_service.download_cover()
  als local_cover_path leeg is; thumbnail max 300x450, JPEG q=85.


==================================================
9. ZOEKLOGICA (WISHLIST)
==================================================

Bestand: src/services/wishlist_service.py

Drie modi, corresponderend met de drie knoppen in het UI-boekmenu:

A. Full Search        (search_book_full)
B. Title Search       (search_book, search_type="title")
C. Author Search      (search_book, search_type="author")
D. Background Search  (search_books, aangeroepen door BackgroundService)

A. FULL SEARCH
--------------
1. Directe title-search via spotweb_service.search_books(book.title).
2. Directe author-search via spotweb_service.search_books(book.author).
3. Resultaten combineren op guid (dict).
4. Voor elk resultaat: book_matches(title, author, spot_title, "").
   (= titel + auteur beide aanwezig in de Spot-titel.)
5. Als GEEN directe match: package search als fallback.
   - Keywords uit settings.wishlist.description_search_keywords.
   - Voor elk keyword: spotweb_service.search_books(keyword).
   - Voor elk resultaat: get_details(guid) → description.
   - Match via book_matches(book.title, book.author, spot_title, description).
6. Nieuwe records aanmaken, gekoppeld aan book.id, search_type=BOOK.
7. book.status = POSSIBLE_MATCH als er matches zijn.
8. Deduplicatie: op (book_id, guid, search_type).

B. TITLE SEARCH
---------------
1. spotweb_service.search_books(book.title).
2. In aanvulling: package search met search_type="title".
   - Per package: get_details, description splitsen op regels.
   - match_title_or_author(book.title, book.author, line).
3. Nieuwe records met book_id=NULL, search_type=TITLE.
4. book.status wordt NIET gewijzigd (bewuste keuze, zie sectie 17).

C. AUTHOR SEARCH
----------------
Idem als B, met book.author, search_type=AUTHOR, book_id=NULL.

D. BACKGROUND SEARCH
--------------------
1. Boeken met status UNAVAILABLE ophalen.
2. spotweb_service.fetch_recent_books_paginated(pages=3, page_size=100)
   = 300 recente releases.
3. Per boek, per resultaat:
   a. book_matches(book.title, book.author, spot_title, "").
      → direct match.
   b. Als geen match: check of de Spot-titel een package-keyword bevat
      (uit description_search_keywords). Zo nee → skip.
   c. Zo ja: get_details(guid), dan book_matches(..., details.description).
4. Nieuwe records met book_id=book.id, search_type=BOOK.
5. book.status = POSSIBLE_MATCH als er matches zijn.

Efficiency-detail (belangrijk t.o.v. v02):
In de background search wordt get_details NIET opgehaald voor ieder
resultaat. Alleen als de Spot-titel een package-keyword bevat. Dit
voorkomt onnodige detail-requests.

Zie ook de tabel onderaan sectie 9 (zoekmodi).


==================================================
10. BOOK MATCHING
==================================================

Bestand: src/services/bookmatch_service.py

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

Bestand: src/services/background_service.py

BackgroundService start in FastAPI lifespan:
- download_status_worker
- wishlist_search_worker

download_status_worker:
- Loop: lees settings.background.download_status_interval (>=15s).
- Slaap interval, dan alle SearchResultRecord met
  download_status=DOWNLOADING checken via downloads_service.
- check_download_status() werkt book.status bij (DOWNLOADING /
  DOWNLOADED / DOWNLOAD_FAILED) voor gekoppelde book_id's.

wishlist_search_worker:
- Eerste iteratie direct (geen wachttijd), daarna interval
  (settings.background.wishlist_search_interval, >=300s).
- Roept wishlist_service.search_books(session) aan.
- Logt "Automatic Search Completed" via log_background_task().
- Bij fout: "Automatic Search Failed".

manual_wishlist_search():
- Wordt getriggerd door /wishlist/search (POST).
- Dedupliceert: als er al een manual task loopt, doet hij niets.
- Gebruikt asyncio.Lock (wishlist_search_lock) zodat manual en
  automatic search niet tegelijk lopen.

Blocking werk (Spotweb-calls, SQLModel) draait via asyncio.to_thread
zodat de event loop vrij blijft.

ActivityLogService.log_background_task():
- Dedupliceert "Automatic Search Completed": werkt bestaande regel bij
  in plaats van nieuwe aan te maken. Voorkomt onbeperkte groei van het
  log bij de periodieke search.

BELANGRIJK: De activity log kan bij frequent manueel gebruik snel vullen
(INFO per zoekopdracht in search_book title/author). Zie sectie 15.


==================================================
12. UI / UX
==================================================

Base layout: src/templates/pulsarr/index.html
- Sidebar-navigatie (Library / Wishlist / Result Management /
  Activity Log / Configuration).
- Mobile menu met off-canvas sidebar.
- Versie-footer met "v0.8.9" (hardcoded — zie sectie 15).
- Bootstrap CSS/JS via CDN (zie sectie 4.2 punt 3).

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
  TITLE → search_title
  AUTHOR → search_author
  BOOK → "author - title" (of één van beide)

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
- Eigen CSS-laag in pulsarr.css (design tokens, knoppen, tiles,
  library-grid, mobile menu, status-badges).
- Gebruikt moderne CSS (:has()) — vereist Chromium 105+, Safari 15.4+,
  Firefox 121+. Houd hier rekening mee bij browser-compatibiliteit.
- Geen dark mode (bewust niet aanwezig).
- Taalmix NL/EN in UI-teksten (cosmetisch).

Client-side vs server-side filtering (bewust niet uniform):
- Activity Log    → client-side
- Result Management → client-side
- Wishlist        → client-side
- Library         → server-side (debounced)

Modals gebruiken textContent (niet innerHTML) — dit is bewust, want
beschrijvingen kunnen HTML bevatten. NIET wijzigen zonder escaping-laag.


==================================================
13. DEPLOYMENT
==================================================

Dockerfile:
- Base: python:3.14-slim
- ENV: PULSARR_CONFIG_DIR=/config, PULSARR_LIBRARY_ROOT=/library
- mkdir -p /config /library
- CMD: uvicorn src.main:app --host 0.0.0.0 --port 8010
- EXPOSE 8010

Aandachtspunten:
- Container draait als root (geen USER-directive). Overwegen om
  naar non-root te gaan (security-best-practice).
- Geen HEALTHCHECK.
- Geen multi-stage build.
- Base image python:3.14 is erg recent; controleer compatibiliteit
  met Pillow en SQLModel.

.dockerignore sluit config/, data/, library/, *.db, *.sqbpro uit
(geen secrets of data in image). Let op: *.sqbpro lijkt een typefout
voor *.sqlite of *.db-shm/.db-wal; controleer.

.gitignore sluit config/config.json en config/*.db uit.
LET OP: .env-bestanden zijn NIET expliciet ignored. Overwegen toe te voegen.

GitHub Actions: .github/workflows/docker.yml
- Trigger: push tags v*
- Permissions: contents:read, packages:write
- Image: ghcr.io/robwiesener/pulsarr
- Platforms: linux/amd64, linux/arm64
- Build via Buildx.
- Actions: checkout@v6, setup-buildx-action@v3, login-action@v4,
  metadata-action@v6, build-push-action@v7.

GHCR is de image-registry.


==================================================
14. RELEASEPROCES
==================================================

Gewenste workflow:

1. Code wijzigen.
2. git diff --check
3. python -m compileall -q src
4. Handmatige functionele tests (relevante zoekmodi, config, UI).
5. git diff controleren.
6. Committen.
7. Versie bijwerken:
   - src/templates/pulsarr/index.html (sidebar-footer)
   - eventueel andere plekken waar versie expliciet staat
8. Tag maken/verplaatsen indien nodig.
9. main pushen.
10. Version-tag pushen → GitHub Actions bouwt Docker image naar GHCR.

Bij bestaande remote tag: voorzichtig. Verplaatsen vereist
`git push --force origin <tag>` en kan andere consumers breken.


==================================================
15. OPENSTAANDE PUNTEN (geconsolideerd)
==================================================

Security (zie ook sectie 4.2 voor details):
1. API-key-lek via exception-strings in logs en UI.
2. API-keys zichtbaar in config-HTML (value-attribuut).
3. CDN zonder SRI (Bootstrap, Bootstrap Icons).
4. Destructieve acties zonder tweede bevestiging (sync_calibre, bulk-download).
5. Geen CSRF op POST-routes.
6. Geen pad-whitelist in /library/cover/{book_id}.
7. Geen security headers (CSP, X-Frame-Options, etc.).
8. Geen `iss`-claim-validatie in CF JWT-check.
9. Docker draait als root.
10. .env niet in .gitignore.

Architectuur / robuustheid:
11. src/db/downloads.py is dode code (niet geïmporteerd in main.py).
    Bevat een dubbele /result-management-route (met template
    downloads/index.html, dat niet bestaat).
12. test_prowlarr.py importeert niet-bestaande src.services.prowlarr_service.
13. test_spotweb_rss.py heeft hardcoded IP (192.168.1.30).
14. test_spotweb_download.py heeft hardcoded RECORD_ID = 4.
15. Routers schenden op enkele plekken de "geen DB in router"-regel
    (activity_log.py, library.py, wishlist.py).
16. Status[status] (Enum-lookup met string) → KeyError → 500 bij
    ongeldige input. Geen nette 400.
17. SpotwebService._log() opent zijn eigen Session(engine) i.p.v.
    session van caller te ontvangen.
18. library_storage_service.py leest config in __init__ op import-tijd
    (wijzigingen in storage.root_dir pas effectief na restart).
19. library_id=04.Calibre is hardcoded in calibre_service.
20. download_status_worker gebruikt sleep als eerste actie; eerste
    status-check pas na interval.
21. download_service.check_download_status() heeft inconsistent
    return-type (tuple vs None).
22. count_books() doet len(...all()) i.p.v. select(func.count()).

Operationeel:
23. Activity log kan snel vullen bij frequent manual search (INFO per
    zoekopdracht title/author).
24. Veel print()-statements in services i.p.v. activity_log_service.
    Functioneel (Docker stdout) maar inconsistent.
25. requirements.txt is niet gepind.
26. Geen HEALTHCHECK in Dockerfile.
27. Versie "v0.8.9" hardcoded in pulsarr/index.html — mogelijk verouderd
    t.o.v. de daadwerkelijke feature-set. Overwegen te bumpen vóór
    volgende release.
28. max-scale=1.0 in viewport (a11y: pinch-zoom geblokkeerd).
29. Taalmix NL/EN in UI-teksten.
30. library_cover is de enige "cover"-route; epub-serving ontbreekt
    (epub_url en local_epub_path worden wel opgeslagen).


==================================================
16. NIET ZOMAAR WIJZIGEN
==================================================

De volgende zaken zijn gevoelig en mogen niet zonder expliciete opdracht
worden aangepast:

- Cloudflare-validatie (src/cloudflare.py) en de CF-headers-detectie.
- De LAN-bypass-keuze (bewust ontwerp, met bekende risico's).
- Spotweb endpoint-opbouw (_get_api_url guard).
- API-key handling in config_service (env-overrides).
- Package-fallback-logica (wishlist_service._search_package_matches).
- Book matching (bookmatch_service) — _normalize, _author_variants,
  match_title_or_author, book_matches.
- SearchResultRecord deduplicatie-logica (per search_type verschillend).
- De bewuste keuze dat title/author searches book_id=NULL hebben en
  book.status niet wijzigen.
- SABnzbd-integratie en status-mapping.
- Calibre-integratie en sync-gedrag (inclusief destructieve delete-stap).
- Achtergrondtaken (locks, to_thread, deduplicatie van "Completed"-log).
- Config.json-architectuur en env-var overrides.
- SQLite-schema.
- Router/service-scheiding (voor zover aanwezig).
- Docker-platforms (amd64 + arm64), image-naam (ghcr.io/robwiesener/pulsarr),
  GitHub Actions tag-trigger (v*).
- Bestaande Bootstrap/Jinja2 UI-structuur.
- Gebruik van textContent (niet innerHTML) in modals.
- Jinja2 auto-escape niet uitzetten (|safe niet toevoegen aan user-content).


==================================================
17. DELTA T.O.V. v02
==================================================

Deze sectie is bedoeld om te controleren of niets belangrijks ontbreekt
wanneer je vanuit v02 verder werkt.

SECURITY (grootste wijziging)
-----------------------------
+ Cloudflare Access JWT-validatie met caching (src/cloudflare.py).
+ LAN-bypass voor private IP-ranges (bewust, gedocumenteerd).
+ Fail-safe: publiek IP zonder CF-headers → JWT verplicht.
+ CF_ACCESS_DISABLED env-var voor lokale dev.
+ Alle routers achter Depends(validate_cloudflare).
+ Env-var overrides voor SPOTWEB_API_KEY en SABNZBD_API_KEY.
+ 0o600 op config.json.
+ .dockerignore sluit config/, data/, library/ uit.

FEATURES (nieuw of aanzienlijk uitgebreid)
------------------------------------------
+ Library-tabel en -sync (Calibre OPDS, cover-download + thumbnail).
+ Library-UI (grid, sorteren, filteren, pagineren, modal).
+ Activity Log-UI met level-badges en vrije-tekst-zoekfilter.
+ Uitgebreide config-pagina met vijf secties (Calibre, Spotweb,
  SABnzbd, Background, Wishlist), elk met save/test, plus sync_calibre.
+ Wishlist-actiemenu met drie zoekmodi (book/title/author) + edit +
  delete + add-by-author.
+ Result Management met bulk-download en bulk-delete, size-weergave,
  modal voor volledige Spot-titel.
+ Background search met keyword-voorfilter (efficiëntie).
+ Manual wishlist search met deduplicatie + asyncio.Lock.
+ "Automatic Search Completed"-deduplicatie in ActivityLogService.
+ DownloadStatus-enum (nieuw) los van Status-enum.
+ SearchType-enum (BOOK/TITLE/AUTHOR).
+ badge_class-property op enums stuurt UI-kleuren.
+ Book-model versimpeld (geen series-velden meer, ondanks docstring).
+ SearchResultRecord uitgebreid: book_id, search_title, search_author,
  search_type, download_status, sabnzbd_id.
+ SpotwebResult dataclass (naast SearchResult).
+ Library-model met calibre_id + lokale bestandspaden.
+ StorageSettings, WishlistSettings, BackgroundSettings.
+ Mobiele CSS-laag met off-canvas sidebar.
+ Library-paginatie + rating-filter.
+ Versie-footer in sidebar (v0.8.9).

ARCHITECTUUR / GEDRAG
---------------------
~ title/author searches maken book_id=NULL en wijzigen book.status NIET
  (in v02 impliciet anders beschreven).
~ Background search checkt keyword-voorfilter vóór get_details.
~ match_package_description splitst op <br> én newlines (robuuster).
~ _author_variants keert woordvolgorde om.
~ search_book_full retourneert None (alleen gelogd).
~ Activity logt nu INFO per title/author search.
~ Book matching: book_matches combineert titel-match en package-match.

OBSOLETE / DODE CODE
--------------------
- src/db/downloads.py is niet meer geïmporteerd in main.py.
  Bevat een dubbele /result-management-route (met niet-bestaande
  template downloads/index.html). Opruimen.
- test_prowlarr.py verwijst naar src.services.prowlarr_service
  (bestaat niet in de huidige codebase).
- In result_management/index.html wordt selectAll gerefereerd maar
  bestaat niet in de template (dode JS).

NIET MEER AANWEZIG (t.o.v. v02-omschrijving)
--------------------------------------------
- De v02-zin "Bootstrap voor UI-layout" is te simpel: er is nu een
  eigen design system in pulsarr.css bovenop Bootstrap.
- Hardcoded IP-adressen (192.168.1.30) zijn weg uit de applicatie
  (staan alleen nog in test_spotweb_rss.py, dev-script).
- Geen aparte SPA, geen frontend-bundler (ongewijzigd t.o.v. v02).


==================================================
18. VALIDATIE BIJ WIJZIGINGEN
==================================================

Standaard uitvoeren bij elke wijziging:

  git diff --check
  python -m compileall -q src

Daarna handmatig testen:
- relevante zoekmodus (full / title / author / background)
- config-pagina (save + test per sectie)
- library-sync (indien geraakt)
- result management (download + delete)
- activity log (indien logging geraakt)
- Cloudflare-validatie:
   * LAN-toegang zonder CF-headers moet werken.
   * CF-headers aanwezig zonder geldige JWT moet 400/401 geven.
   * CF_ACCESS_DISABLED=1 moet alles doorlaten.

Lokaal starten (voorbeeld):
  cd /Volumes/Data/01.Temp/pulsarr
  source .venv/bin/activate
  export PULSARR_CONFIG_DIR=config
  uvicorn src.main:app --reload --host 0.0.0.0 --port 8010

Daarna git diff controleren en pas dan committen.


==================================================
19. DOEL VOOR DE NIEUWE CHAT
==================================================

De nieuwe ChatGPT-chat moet dit document behandelen als de actuele
technische context van Pulsarr.

De gebruiker wil de app verder ontwikkelen vanuit de bestaande codebase,
zonder bestaande functionaliteit onnodig te herschrijven.

Bij twijfel:
- eerst de daadwerkelijke bestanden/code laten bekijken;
- niet aannemen dat een functie anders werkt dan hierboven beschreven;
- geen grote refactor voorstellen als een kleine wijziging voldoende is;
- geen versie verhogen tenzij de gebruiker dat expliciet wil (maar zie
  openstaand punt 27 over de verouderde versie-string);
- geen nieuwe database-migratie introduceren tenzij technisch noodzakelijk;
- bestaande release- en Docker-workflow respecteren;
- security-bevindingen uit sectie 4.2 en 15 niet stilzwijgend negeren:
  als een wijziging raakt aan logging, exceptions, config-UI, CDN-loading
  of POST-routes, de betreffende punten expliciet benoemen.