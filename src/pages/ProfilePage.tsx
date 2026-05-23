import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { readUserFile } from '../lib/github';

// LEARNING EXERCISE — see docs/learning-notes.md
//
// This page should display a user's logged films, newest first. The data
// loading is already wired up; your job is to render `data.logs` nicely.
//
// Hints:
//   - Sort by `logged_at` descending
//   - Show poster, title, rating (★★★★☆), watched_on date, and review
//   - Use IMG(poster_path) from '../lib/tmdb' to build the image URL
//   - Handle the empty state (no logs yet) and the "user doesn't exist" case
//     (data === null)

export default function ProfilePage() {
  const { username } = useParams<{ username: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['user', username],
    queryFn: () => readUserFile(username!),
    enabled: !!username,
  });

  if (isLoading) return <p className="text-zinc-400">Loading…</p>;
  if (error) return <p className="text-red-400">{(error as Error).message}</p>;

  if (!data) {
    return (
      <p className="text-zinc-400">
        No profile found for <code>{username}</code> yet.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{data.display_name}</h1>
      <p className="text-zinc-400">
        {data.logs.length} log{data.logs.length === 1 ? '' : 's'}
      </p>
      <div className="p-4 border border-dashed border-zinc-700 rounded text-zinc-400 text-sm">
        👉 Log list rendering goes here — see docs/learning-notes.md.
      </div>
    </div>
  );
}
