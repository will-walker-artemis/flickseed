import { useState } from 'react';
import { useCurrentUser, setCurrentUser, signOut } from '../lib/auth';

export default function SettingsPage() {
  const user = useCurrentUser();
  const [username, setUsername] = useState(user?.username ?? '');
  const [token, setToken] = useState(user?.token ?? '');
  const [saved, setSaved] = useState(false);

  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold">Settings</h1>

      <p className="text-zinc-400 text-sm">
        Flickseed has no server. Your "account" is just a username (which JSON file in{' '}
        <code>data/users/</code> you write to) plus a GitHub Personal Access Token used to
        commit changes. Both are stored in this browser's localStorage.
      </p>

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          setCurrentUser(username.trim(), token.trim());
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
        }}
      >
        <div>
          <label className="block text-sm mb-1">Username</label>
          <input
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. will"
            required
          />
          <p className="text-xs text-zinc-500 mt-1">
            Your logs will be saved to <code>data/users/{username || '<username>'}.json</code>.
          </p>
        </div>

        <div>
          <label className="block text-sm mb-1">GitHub Personal Access Token</label>
          <input
            type="password"
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 font-mono text-sm"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="ghp_…"
          />
          <p className="text-xs text-zinc-500 mt-1">
            Needs <code>contents:write</code> on this repo. See{' '}
            <a
              href="https://github.com/settings/tokens?type=beta"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              github.com/settings/tokens
            </a>
            .
          </p>
        </div>

        <div className="flex gap-3">
          <button className="bg-zinc-100 text-zinc-900 rounded px-4 py-2 font-medium">
            Save
          </button>
          {user && (
            <button
              type="button"
              onClick={signOut}
              className="border border-zinc-700 rounded px-4 py-2"
            >
              Sign out
            </button>
          )}
          {saved && <span className="text-green-400 self-center text-sm">Saved.</span>}
        </div>
      </form>
    </div>
  );
}
