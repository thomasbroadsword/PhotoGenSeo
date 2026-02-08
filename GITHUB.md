# Utworzenie repozytorium PhotoGenSeo na GitHubie

Repozytorium Git jest już zainicjowane lokalnie (branch `main`, pierwszy commit). Aby mieć kopię na GitHubie:

## 1. Utwórz puste repozytorium na GitHubie

1. Wejdź na [github.com/new](https://github.com/new).
2. **Repository name:** `PhotoGenSeo`.
3. Opis (opcjonalnie): np. *Opisy produktów ze zdjęć (EAN, Claude, Vercel)*.
4. Wybierz **Private** (użytkowanie wewnętrzne) lub **Public**.
5. **Nie** zaznaczaj "Add a README" ani "Add .gitignore" – projekt już je ma.
6. Kliknij **Create repository**.

## 2. Podłącz zdalne repozytorium i wypchnij kod

W terminalu, w katalogu projektu:

```bash
cd /Users/tomasz/Desktop/Cursor/PhotoGenSeo

# Podmień YOUR_USERNAME na swoją nazwę użytkownika GitHub
git remote add origin https://github.com/YOUR_USERNAME/PhotoGenSeo.git

# Wypchnięcie na GitHub
git push -u origin main
```

Jeśli używasz SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/PhotoGenSeo.git
git push -u origin main
```

Po wykonaniu tych kroków repozytorium **PhotoGenSeo** będzie dostępne na Twoim GitHubie.
