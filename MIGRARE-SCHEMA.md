# Pași pentru trecerea la schema nouă (user_id)

Dacă ai deja aplicația deployată cu schema veche (erori de tip „value out of int32 range” la al doilea user), urmează pașii de mai jos. **Toate datele din baza de date vor fi șterse**; utilizatorii vor trebui să se înregistreze din nou din Mini App.

---

## Pasul 1: Salvează `DATABASE_URL` de pe Render

1. Intră pe [Render Dashboard](https://dashboard.render.com).
2. Deschide serviciul tău (ex. **foodtracker**).
3. Mergi la **Environment**.
4. Găsești variabila **DATABASE_URL** (connection string-ul Neon). Copiază-l într-un loc sigur (Notepad, 1Password etc.) — îl vei folosi la Pasul 3.

---

## Pasul 2: Push la codul actual pe GitHub

Asigură-te că ai făcut push la toate modificările (inclusiv schema cu `user_id`, `telegram_id` ca string etc.) pe branch-ul pe care îl folosești pe Render (de obicei `main`):

```bash
git add -A
git commit -m "Schema user_id: telegram_id string, tabele cu user_id"
git push origin main
```

---

## Pasul 3: Ștergerea tabelelor vechi din Neon (reset schema)

Trebuie șterse tabelele vechi ca, la următorul start, aplicația să le recreeze cu schema nouă.

### Varianta A: Script Python (recomandat)

Pe calculatorul tău, în folderul proiectului:

1. Creează un fișier `.env` în rădăcina proiectului (dacă nu există) și pune în el:
   ```env
   DATABASE_URL=postgresql://user:parola@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```
   (înlocuiești cu connection string-ul copiat de pe Render / Neon).

2. Rulează:
   ```bash
   python scripts/reset_schema.py
   ```
   Scriptul va cere confirmare (scrii `yes`). După rulare, toate tabelele sunt șterse și recreate cu schema nouă.

### Varianta B: Din Neon SQL Editor

1. Intră pe [Neon Console](https://console.neon.tech), deschide proiectul tău.
2. Mergi la **SQL Editor**.
3. Rulează următoarea comandă (șterge toate tabelele app-ului):
   ```sql
   DROP TABLE IF EXISTS water_intake, workouts, foods, daily_calories, weight_history, users CASCADE;
   ```
4. Apasă **Run**. Tabelele dispar; la următorul start al aplicației pe Render ele vor fi create din nou cu schema nouă.

---

## Pasul 4: Redeploy pe Render

1. În Render, la serviciul tău: **Manual Deploy** → **Deploy latest commit** (sau așteaptă deploy-ul automat după push).
2. Așteaptă până deploy-ul este **Live**.
3. La primul request, aplicația rulează `create_all` și creează tabelele cu noua schemă (`users.telegram_id` string, restul tabelelor cu `user_id`).

---

## Pasul 5: Verificare

1. Deschide Mini App-ul din Telegram (Menu → aplicația ta).
2. Dacă erai deja „înregistrat” în schema veche, cel mai simplu e să deschizi aplicația ca un **utilizator nou** (alt cont Telegram) sau să te asiguri că înregistrarea se face din nou (flow-ul de onboarding).
3. Adaugă o masă, apă, greutate — ar trebui să meargă fără erori de integer/range.

După acești pași, aplicația folosește schema cu `user_id` intern (1, 2, 3…) și `telegram_id` stocat ca string; problema de int32/int64 dispare.
