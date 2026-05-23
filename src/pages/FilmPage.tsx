import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getFilm, IMG } from '../lib/tmdb';
import { useCurrentUser } from '../lib/auth';

// LEARNING EXERCISE — see docs/learning-notes.md
//
// This page renders the film's basic details. Your job is to add a log form
// below: date watched, 1–5 rating, short review. When submitted it should
// call `writeUserFile()` from src/lib/github.ts to append a LoggedFilm to the
// current user's JSON file in `data/users/<username>.json`.
//
// Hints:
//   - useCurrentUser() gives you { username, token } (or null if not set up)
//   - readUserFile(username) fetches the current logs (may be null first time)
//   - useMutation from @tanstack/react-query is the idiomatic way to wrap the
//     write call so you get loading/error state for free
//   - After a successful write, invalidate the ['user', username] query so
//     the profile page picks it up

export default function FilmPage() {
  const { id } = useParams<{ id: string }>();
  const user = useCurrentUser();

  const { data: film, isLoading, error } = useQuery({
    queryKey: ['film', id],
    queryFn: () => getFilm(id!),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-zinc-400">Loading…</p>;
  if (error) return <p className="text-red-400">{(error as Error).message}</p>;
  if (!film) return null;

  return (
    <div className="grid md:grid-cols-[200px_1fr] gap-6">
      <div className="aspect-[2/3] bg-zinc-900 rounded overflow-hidden">
        {film.poster_path && (
          <img src={IMG(film.poster_path, 'w342') ?? ''} alt={film.title} />
        )}
      </div>
      <div className="space-y-3">
        <h1 className="text-2xl font-bold">
          {film.title}{' '}
          <span className="text-zinc-400 font-normal">
            ({film.release_date?.slice(0, 4)})
          </span>
        </h1>
        {film.tagline && <p className="italic text-zinc-400">{film.tagline}</p>}
        <p>{film.overview}</p>
        <div className="text-sm text-zinc-400">
          {film.runtime ? `${film.runtime} min` : ''}
          {film.genres?.length ? ` · ${film.genres.map((g) => g.name).join(', ')}` : ''}
        </div>

        <div className="mt-6 p-4 border border-dashed border-zinc-700 rounded text-zinc-400 text-sm">
          {user
            ? '👉 Log form goes here — see docs/learning-notes.md for the exercise.'
            : 'Set up your profile in Settings to log this film.'}
        </div>
      </div>
    </div>
  );
}
