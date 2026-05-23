import { Link } from 'react-router-dom';
import { useCurrentUser } from '../lib/auth';

export default function HomePage() {
  const user = useCurrentUser();
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Flickseed</h1>
      <p className="text-zinc-400">
        A tiny Letterboxd-style film log. Search TMDB, mark films watched, rate them, and write
        short reviews. Data lives as JSON files in this repo.
      </p>
      {!user && (
        <p>
          <Link to="/settings" className="underline">
            Set up your profile
          </Link>{' '}
          to start logging films.
        </p>
      )}
      <p>
        <Link to="/search" className="underline">
          Search for a film &rarr;
        </Link>
      </p>
    </div>
  );
}
