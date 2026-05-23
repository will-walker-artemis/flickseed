import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { searchFilms, IMG } from '../lib/tmdb';

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get('q') ?? '';
  const [input, setInput] = useState(query);

  const { data, isFetching, error } = useQuery({
    queryKey: ['search', query],
    queryFn: () => searchFilms(query),
    enabled: query.length > 0,
  });

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setParams(input ? { q: input } : {});
        }}
        className="flex gap-2"
      >
        <input
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2"
          placeholder="Search for a film…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          autoFocus
        />
        <button className="bg-zinc-100 text-zinc-900 rounded px-4 py-2 font-medium">
          Search
        </button>
      </form>

      {error && <p className="text-red-400">{(error as Error).message}</p>}
      {isFetching && <p className="text-zinc-400">Searching…</p>}

      {data && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {data.results.map((film) => (
            <li key={film.id}>
              <Link to={`/film/${film.id}`} className="block group">
                <div className="aspect-[2/3] bg-zinc-900 rounded overflow-hidden">
                  {film.poster_path ? (
                    <img
                      src={IMG(film.poster_path) ?? ''}
                      alt={film.title}
                      className="w-full h-full object-cover group-hover:opacity-80 transition"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-zinc-600 text-xs">
                      No poster
                    </div>
                  )}
                </div>
                <div className="mt-2 text-sm">
                  <div className="font-medium line-clamp-2">{film.title}</div>
                  <div className="text-zinc-400">{film.release_date?.slice(0, 4)}</div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
