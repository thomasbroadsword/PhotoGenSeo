# PhotoGenSeo

Zaawansowany system wyciągania danych ze zdjęć produktów na podstawie kodu EAN: identyfikacja produktu → wyszukiwanie źródeł (SerpAPI / DuckDuckGo) → pobieranie zdjęć → **AI matching** (potwierdzenie, że to ten sam produkt) → odrzucanie wątpliwych źródeł i zdjęć niewnoszących unikalności → analiza przez **Claude Vision** → **weryfikacja opisu** oraz ekstrakcja EAN i wymiarów ze zdjęć → opis bazowy pod generację SEO.

## Przepływ

1. **Identyfikacja po EAN** – Open Food Facts (darmowe) + opcjonalnie EAN-DB (JWT).
2. **Wyszukiwanie źródeł** – SerpAPI (Google Images + wyniki organiczne Google), fallback DuckDuckGo Images.
3. **Pobieranie** – min. 10 zdjęć do katalogu `data/images/`.
4. **Analiza kosztów** – przed generowaniem opisu szacowany jest koszt (Claude API, tokeny/obrazy). Zapis do bazy (Vercel Postgres) z `cost_estimate` i `run_id`. Opcja `--estimate-only`: tylko koszt, bez wywołań Claude.
5. **AI matching produktów** – Claude ocenia, czy zdjęcia przedstawiają ten sam produkt (ten sam EAN); odrzucane są inne produkty i zdjęcia wątpliwe.
6. **Odrzucanie wątpliwych** – ocena unikalności zdjęcia i wiarygodności źródła; odrzucane zdjęcia duplikatowe, mockupy, źródła niewiarygodne.
7. **Analiza zdjęć** – Claude Vision generuje opis bazowy (podstawa pod SEO).
8. **Weryfikacja opisu** – zweryfikowany opis + wyciąganie z zdjęć: **EAN** (gdy czytelny), **wymiary**, objętość/waga (gdy widoczne na etykiecie/opakowaniu).
9. **Wynik** – `data/output/{EAN}/result.json`, `description.txt`; opcjonalnie baza (Vercel Postgres): run + tylko pomniejszone zdjęcia wykorzystane.

## Konfiguracja

Skopiuj `.env.example` do `.env` i uzupełnij:

- **ANTHROPIC_API_KEY** (wymagane) – do analizy zdjęć i weryfikacji (Claude).
- **SERPAPI_API_KEY** (opcjonalne) – Google Images + wyniki Google; bez klucza używany jest DuckDuckGo.
- **EAN_DB_JWT** (opcjonalne) – rozszerzona baza produktów (EAN-DB).
- **POSTGRES_URL** (opcjonalne) – baza na Vercel (Postgres/Neon). Przy Vercel PRO: dodaj Postgres z Marketplace; zmienna jest wstrzykiwana automatycznie. Zapis: runy (EAN, szacunek kosztów, wynik) oraz pomniejszone zdjęcia **tylko tych wykorzystanych** w pipeline.

Progi w `config.py`:

- `PRODUCT_MATCH_MIN_CONFIDENCE` – minimalna pewność, że zdjęcie to ten sam produkt (domyślnie 0.75).
- `IMAGE_UNIQUENESS_MIN_SCORE` – minimalna „unikalność” zdjęcia (poniżej = odrzuć).
- `SOURCE_TRUST_MIN_SCORE` – minimalna wiarygodność źródła.

## Aplikacja webowa (Vercel)

Aplikacja do użytku wewnętrznego na Vercel:

- **Wsadowe generowanie** – max 10 produktów na raz (lista EAN).
- **Walidacja wzrokowa** – wstępnie wybrane zdjęcia z wyszukiwania; użytkownik zaznacza/odznacza zdjęcia. W razie braku: przycisk **„Szukaj więcej zdjęć”** (kolejna porcja z sieci).
- **Wgrywanie własnych zdjęć** – przycisk „Wgraj zdjęcia” per produkt.
- **Eksport CSV** – po wygenerowaniu opisów: EAN, nazwa, opis, EAN ze zdjęć, wymiary, objętość/waga.

Uruchomienie lokalne:

```bash
npm install
npm run dev
```

Frontend: `http://localhost:3000`. API w Pythonie: `api/batch_search.py`, `api/search_more.py`, `api/run_from_images.py` (na Vercel działają jako serverless pod `/api/...`).

Deploy na Vercel: połącz repozytorium, ustaw zmienne środowiskowe (ANTHROPIC_API_KEY, SERPAPI_API_KEY itd.). Build: Next.js; funkcje Python z folderu `api/` są automatycznie wdrażane.

### Vercel Password Protection

Ochrona hasłem (dla użytku wewnętrznego) włącza się w panelu Vercel – bez zmian w kodzie. Dostępna na planie **Enterprise** lub z add-onem **Advanced Deployment Protection** na planie Pro ([docs](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/password-protection)).

1. W [Vercel Dashboard](https://vercel.com/dashboard) wybierz projekt **PhotoGenSeo**.
2. **Settings** → **Deployment Protection**.
3. W sekcji **Password Protection**:
   - Włącz toggle.
   - Wybierz środowisko (Production, Preview lub oba).
   - Wpisz hasło i kliknij **Save**.

Odwiedzający deployment muszą podać hasło (raz na dany URL – Vercel ustawia ciasteczko). Zmiana hasła wymaga ponownego logowania.

## Uruchomienie CLI

```bash
pip install -r requirements.txt
python main.py 5901234123457
```

Opcje:

- `--min-images 12` – min. liczba zdjęć do wyszukania.
- `--output-subdir nazwa` – zapis do `data/output/nazwa/` zamiast `data/output/{EAN}/`.
- **`--estimate-only`** – tylko analiza kosztów: pobierz zdjęcia, oszacuj koszt (i zapisz run do bazy jeśli POSTGRES_URL), **bez** wywołań Claude (generacja opisu). Przydatne przed pełnym pipeline’em.
- `--no-db` – nie zapisuj do bazy (runy ani zdjęcia).

Inicjalizacja tabel (gdy używasz bazy):

```bash
python -c "from src.db import init_tables; init_tables()"
```

## Struktura projektu

- `config.py` – ścieżki, klucze API, progi.
- `main.py` – wejście CLI.
- `src/source_search.py` – SerpAPI (obrazy + organic) + DuckDuckGo.
- `src/image_downloader.py` – pobieranie zdjęć.
- `src/product_matching.py` – AI matching (ten sam produkt).
- `src/quality_filter.py` – odrzucanie wątpliwych źródeł i zdjęć bez wartości.
- `src/image_analyzer.py` – opis bazowy z zdjęć (Claude Vision).
- `src/description_verification.py` – weryfikacja opisu, EAN, wymiary.
- `src/cost_estimate.py` – szacowanie kosztów (tokeny/obrazy) przed generowaniem.
- `src/db.py` – Vercel Postgres: `pipeline_runs`, `product_images` (tylko pomniejszone, wykorzystane zdjęcia).
- `src/image_store.py` – pomniejszanie zdjęć przed zapisem do bazy.
- `src/pipeline.py` – orkiestracja pełnego pipeline’u.

Wyniki: `data/output/{EAN}/result.json` (pełny wynik + `verified.description_verified`, `verified.ean_from_images`, `verified.dimensions_from_images`) oraz `description.txt`.
