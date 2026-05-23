# Flickseed

A tiny Letterboxd-style film log, built as a learn-React project.

Search films via [TMDB](https://www.themoviedb.org/), mark them watched, give them a 1–5 rating, and write a short review. Logs are stored as JSON files in this repo — every rating you make becomes a git commit.

## What it does

- 🔎 Search the TMDB database for films
- 📄 View a film's details (poster, year, runtime, overview)
- ⭐ Mark a film watched with a rating (½ stars) and a short review
- 📚 Browse your own log of watched films

## What it isn't

- No followers / social feed (yet)
- No lists or watchlists (yet)
- No real auth — accounts are just usernames + a personal access token

## How it's wired

- **Frontend:** React + TypeScript, built with Vite, styled with Tailwind v4
- **Hosting:** GitHub Pages (static — no server)
- **Film data:** TMDB REST API, called directly from the browser
- **Your data:** JSON files in `data/users/<username>.json`, read via `raw.githubusercontent.com` and written via the GitHub Contents API

## Quick start

```bash
npm install
cp .env.example .env.local   # then fill in your TMDB key + GH owner/repo
npm run dev
```

## Project layout

```
src/
  main.tsx              # app entry — providers (Query, Router) live here
  App.tsx               # route table
  components/Layout.tsx # header + nav, wraps every page
  pages/                # one file per route
  lib/
    tmdb.ts             # TMDB API client
    github.ts           # read/write JSON files in this repo
    auth.ts             # localStorage-backed "who am I" state
data/
  users/<name>.json     # one file per user; their logs live here
.github/workflows/      # Pages deploy
```
