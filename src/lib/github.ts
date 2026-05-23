// Treats the repo's `data/` directory as the database.
//
// Reads use raw.githubusercontent.com (no auth needed for public repos).
// Writes use the GitHub Contents API and require a PAT with `repo` scope
// (or `contents:write` for fine-grained tokens) — see Settings page.

const OWNER = import.meta.env.VITE_GH_OWNER as string | undefined;
const REPO = import.meta.env.VITE_GH_REPO as string | undefined;
const BRANCH = (import.meta.env.VITE_GH_BRANCH as string | undefined) ?? 'main';

export interface LoggedFilm {
  tmdb_id: number;
  title: string;
  poster_path: string | null;
  watched_on: string;     // ISO date e.g. "2026-05-23"
  rating: number;         // 1..5, half-stars allowed (0.5 step)
  review: string;
  logged_at: string;      // ISO timestamp, when the entry was created
}

export interface UserFile {
  username: string;
  display_name: string;
  logs: LoggedFilm[];
}

function requireRepoConfig() {
  if (!OWNER || !REPO) {
    throw new Error(
      'Missing VITE_GH_OWNER / VITE_GH_REPO. Set these in .env.local and in the deploy workflow.',
    );
  }
  return { owner: OWNER, repo: REPO, branch: BRANCH };
}

// --- Reads -----------------------------------------------------------------

const rawUrl = (path: string) => {
  const { owner, repo, branch } = requireRepoConfig();
  return `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${path}`;
};

export async function readUserFile(username: string): Promise<UserFile | null> {
  // Cache-bust so freshly-written data shows up without a hard refresh.
  const res = await fetch(`${rawUrl(`data/users/${username}.json`)}?t=${Date.now()}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to read ${username}.json: ${res.status}`);
  return res.json() as Promise<UserFile>;
}

// --- Writes ----------------------------------------------------------------

interface ContentsApiFile {
  sha: string;
  content: string;
}

async function getFileMeta(path: string, token: string): Promise<ContentsApiFile | null> {
  const { owner, repo, branch } = requireRepoConfig();
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
    { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } },
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub GET contents failed: ${res.status}`);
  return res.json();
}

// btoa() can't handle multi-byte chars (e.g. emoji in a review). Encode to
// UTF-8 bytes first, then base64.
function toBase64Utf8(input: string): string {
  const bytes = new TextEncoder().encode(input);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

export async function writeUserFile(
  file: UserFile,
  token: string,
  message: string,
): Promise<void> {
  const { owner, repo, branch } = requireRepoConfig();
  const path = `data/users/${file.username}.json`;
  const existing = await getFileMeta(path, token);
  const body = {
    message,
    content: toBase64Utf8(JSON.stringify(file, null, 2) + '\n'),
    branch,
    ...(existing ? { sha: existing.sha } : {}),
  };
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
    {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    throw new Error(`GitHub PUT contents failed: ${res.status} ${await res.text()}`);
  }
}
