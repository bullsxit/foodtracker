## Telegram Calorie & Health Tracker Bot

Acesta este un bot Telegram de tip tracker personal de calorii și sănătate, construit în Python, cu o arhitectură modulară și scalabilă.

### Funcționalități principale

- **Onboarding inițial** cu salvarea profilului utilizatorului (nume, vârstă, înălțime, greutate, obiectiv, nivel de activitate, sex biologic).
- **Calcul automat al caloriilor țintă** folosind formula Mifflin-St Jeor și factori de activitate.
- **Pagina Acasă (🏠 Acasă)**:
  - Adăugare mâncare manual (nume, calorii, macro).
  - Încărcare fotografie cu mâncare și analiză AI mock (calorii + macro).
  - Afișare „Caloriile de azi” (consumate / țintă + câte au rămas).
- **Statistici (📊 Statistici)**:
  - Grafic calorii pe ultimele 7 zile.
  - Grafic calorii pe ultimele 30 de zile.
  - Media caloriilor pe ultimele 7 zile.
- **Jurnal (📖 Jurnal)**:
  - Jurnal alimentar zilnic, grupat pe zile.
  - Navigare cu „Zi precedentă” / „Zi următoare”.
- **Profil (👤 Profil)**:
  - Afișare date profil și progres (greutate inițială, curentă, diferență).
  - Actualizare greutate (salvată și în `WeightHistory`).
  - Schimbare obiectiv.
- **Setări (⚙️ Setări)**:
  - Resetare completă profil (șterge utilizator, istoric greutate, mâncăruri, calorii zilnice).
  - Schimbare date personale (vârstă, înălțime).
  - Schimbare nivel de activitate.

Toată interfața utilizator este în **limba română**. Numele variabilelor, funcțiilor și comentariile din cod sunt în engleză.

### Tehnologii folosite

- Python 3.11+
- `python-telegram-bot` (async)
- SQLite + SQLAlchemy (async, `aiosqlite`)
- `Pillow`
- `httpx` (pregătit pentru integrare AI reală)
- `pandas`
- `matplotlib`
- `python-dotenv`

### Structura proiectului

- `main.py` – punctul de intrare pentru **modul local**: pornește botul în polling și inițializează baza de date.
- `config.py` – încărcare configurări (token, URL bază de date, opțional URL webhook).
- `requirements.txt` – dependențe Python.
- `README.md` – acest fișier.
- `webapp/` – aplicația web (mini app) servită de FastAPI: `server.py`, fișiere statice (HTML/JS/CSS).
- `render.yaml` – configurare pentru host pe Render (opțional).

Foldere:

- `database/`
  - `models.py` – definiții ORM (Users, WeightHistory, Foods, DailyCalories).
  - `database.py` – engine async, factory pentru sesiuni și inițializare tabele.
- `handlers/`
  - `start_handler.py` – onboarding și /start.
  - `home_handler.py` – „Acasă”, mâncare manuală, foto, calorii de azi.
  - `profile_handler.py` – profil utilizator și actualizare greutate/obiectiv.
  - `statistics_handler.py` – generare și trimitere grafice statistici.
  - `history_handler.py` – jurnal zilnic, navigare între zile.
  - `settings_handler.py` – reset profil și modificări de setări.
- `services/`
  - `calorie_ai_service.py` – serviciu AI mock pentru analiză foto.
  - `calorie_calculation_service.py` – calcule BMR și calorii țintă.
  - `statistics_service.py` – interogări și generare grafice cu `matplotlib`.
  - `score_service.py` – scor disciplină și streak (pentru mini app).
  - `water_service.py` – apă zilnică (pentru mini app).
- `utils/`
  - `keyboards.py` – generare tastaturi (ReplyKeyboardMarkup).
  - `validators.py` – parsare și validare input numeric.
  - `helpers.py` – utilitare generale.
- `data/`
  - `database.db` – fișierul SQLite (va fi creat automat la rulare).

---

### Cum creezi un bot Telegram și obții token-ul

1. Deschide aplicația Telegram (desktop sau mobil).
2. Caută utilizatorul `@BotFather`.
3. Trimite comanda `/start` către BotFather.
4. Trimite comanda `/newbot` și urmează instrucțiunile:
   - Alege un nume afișat (ex. „Food Tracker Bot”).
   - Alege un username unic care se termină în `bot` (ex. `foodtracker_personal_bot`).
5. La final, BotFather îți va trimite un **HTTP API token** de forma:
   - `1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ`
6. Păstrează token-ul în siguranță – îl vei folosi în variabila de mediu `TELEGRAM_BOT_TOKEN`.

---

### Cum instalezi dependențele

1. Asigură-te că ai instalat Python 3.11+ (`python3 --version`).
2. Creează și activează un mediu virtual (recomandat):

```bash
cd foodtracker
python3 -m venv .venv
source .venv/bin/activate  # pe macOS / Linux
# .venv\Scripts\activate   # pe Windows PowerShell
```

3. Instalează dependențele:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Configurarea variabilelor de mediu

În rădăcina proiectului creează un fișier `.env`:

```bash
TELEGRAM_BOT_TOKEN=TOKENUL_TAU_DE_LA_BOTFATHER
DATABASE_URL=sqlite+aiosqlite:///data/database.db
```

- `TELEGRAM_BOT_TOKEN` – token-ul de la BotFather.
- `DATABASE_URL` – URL-ul bazei de date SQLite (valoarea implicită funcționează pentru majoritatea cazurilor).

---

### Cum rulezi botul local

1. Asigură-te că mediul virtual este activat (vezi pașii de mai sus).
2. Rulează:

```bash
python main.py
```

3. În Telegram:
   - Caută botul tău după username-ul configurat la BotFather.
   - Apasă „Start” sau trimite comanda `/start`.
   - Urmează pașii de onboarding în limba română.

---

### Rulare locală: bot + mini app (preview în browser)

Pentru a folosi și **mini app-ul** (interfața web pentru calorii, apă, greutate, statistici) pe localhost:

1. **Terminal 1 – Bot (polling)**  
   Din rădăcina proiectului, cu mediul virtual activat:

```bash
cd /calea/ta/foodtracker
source .venv/bin/activate
python main.py
```

2. **Terminal 2 – Server web (FastAPI)**  
   În același proiect, cu același venv activat:

```bash
cd /calea/ta/foodtracker
source .venv/bin/activate
uvicorn webapp.server:app --reload --port 8000
```

3. **Browser**  
   Deschide:

```
http://127.0.0.1:8000/webapp/index.html?tid=TELEGRAM_ID
```

   Înlocuiește `TELEGRAM_ID` cu ID-ul tău Telegram (îl poți obține de la @userinfobot în Telegram). Fără `?tid=...` corect, mini app-ul poate să nu afișeze datele tale.

4. **Variabile de mediu**  
   În `.env` ai nevoie cel puțin de:
   - `TELEGRAM_BOT_TOKEN=...` (obligatoriu pentru ambele procese).
   - `DATABASE_URL=sqlite+aiosqlite:///data/database.db` (opțional; aceasta e valoarea implicită).

   Pentru **doar local**, nu este nevoie de `BOT_WEBHOOK_URL`; se folosește polling din `main.py`. Pentru host (ex. Render), setezi `BOT_WEBHOOK_URL` și atunci botul rulează în mod webhook din uvicorn.

---

### Note de producție

- Codul folosește `asyncio` și `python-telegram-bot` async.
- Baza de date este gestionată cu SQLAlchemy async + SQLite (fișierul `data/database.db`).
- Serviciul AI pentru imagini este mocat în `calorie_ai_service.py` și poate fi înlocuit ușor cu un API real (prin `httpx` sau alt client HTTP).
- **Deploy (ex. Render):** setezi `TELEGRAM_BOT_TOKEN`, `BOT_WEBHOOK_URL`, `DATABASE_URL` (și opțional `OPENAI_API_KEY` / `FOOD_AI_PROVIDER`). Pornești cu `uvicorn webapp.server:app --host 0.0.0.0 --port $PORT`; botul rulează în mod webhook, nu mai este nevoie de `main.py`.
- **Telegram Mini App pentru toți (gratuit):** vezi **[DEPLOY.md](DEPLOY.md)** pentru pași completi: Render (free) + Neon (PostgreSQL free), variabile de mediu, și cum utilizatorii deschid aplicația din Telegram (PC, telefon, tabletă). Clasamentul global funcționează cu aceeași bază de date.
- Pentru un server propriu (VPS), poți rula `python main.py` (polling) sau uvicorn cu webhook, cu systemd, Docker etc.

