import { Outlet, Link, NavLink } from 'react-router-dom';
import { useCurrentUser } from '../lib/auth';

export default function Layout() {
  const user = useCurrentUser();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-zinc-800">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/" className="font-semibold text-lg">
            Flickseed
          </Link>
          <nav className="flex gap-4 text-sm">
            <NavItem to="/search">Search</NavItem>
            {user && <NavItem to={`/u/${user.username}`}>My Logs</NavItem>}
            <NavItem to="/settings">Settings</NavItem>
          </nav>
          <div className="ml-auto text-sm text-zinc-400">
            {user ? `Signed in as ${user.username}` : 'Not signed in'}
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        isActive ? 'text-white' : 'text-zinc-400 hover:text-white'
      }
    >
      {children}
    </NavLink>
  );
}
