// Thin wrapper around the TMDB v3 REST API.
// The key is injected at build time via Vite's `import.meta.env`.
// See docs/setup.md for how to provide it locally vs. in GitHub Actions.

const API_KEY = import.meta.env.VITE_TMDB_API_KEY as string | undefined;
const BASE = 'https://api.themoviedb.org/3';

export const IMG = (path: string | null, size: 'w185' | 'w342' | 'w500' | 'original' = 'w342') =>
  path ? `https://image.tmdb.org/t/p/${size}${path}` : null;

export interface TmdbSearchResult {
  id: number;
  title: string;
  release_date: string;
  poster_path: string | null;
  overview: string;
}

export interface TmdbFilm extends TmdbSearchResult {
  runtime: number | null;
  genres: { id: number; name: string }[];
  tagline: string | null;
  backdrop_path: string | null;
}

async function tmdbFetch<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  if (!API_KEY) {
    throw new Error(
      'Missing VITE_TMDB_API_KEY. Add it to .env.local for dev, or as a GitHub secret for deploys.',
    );
  }
  const url = new URL(BASE + path);
  url.searchParams.set('api_key', API_KEY);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`TMDB ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export function searchFilms(query: string) {
  return tmdbFetch<{ results: TmdbSearchResult[] }>('/search/movie', {
    query,
    include_adult: 'false',
  });
}

export function getFilm(id: number | string) {
  return tmdbFetch<TmdbFilm>(`/movie/${id}`);
}
