import { useState } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  HomeIcon,
  DocumentTextIcon,
  BuildingOffice2Icon,
  TicketIcon,
  IdentificationIcon,
  Bars3Icon,
  XMarkIcon,
  ArrowRightStartOnRectangleIcon,
} from '@heroicons/react/24/outline';

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Claims', href: '/claims', icon: DocumentTextIcon },
  { name: 'Facilities', href: '/facilities', icon: BuildingOffice2Icon },
  { name: 'Tickets', href: '/tickets', icon: TicketIcon },
  { name: 'Credentials', href: '/credentials', icon: IdentificationIcon },
];

const roleBadgeColor: Record<string, string> = {
  super_admin: 'bg-red-100 text-red-700',
  org_admin: 'bg-purple-100 text-purple-700',
  biller: 'bg-blue-100 text-blue-700',
  coder: 'bg-indigo-100 text-indigo-700',
  client: 'bg-green-100 text-green-700',
  auditor: 'bg-gray-100 text-gray-700',
};

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/';
    return location.pathname.startsWith(href);
  };

  const sidebar = (
    <div className="flex flex-col h-full bg-slate-900 text-white w-64">
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-700">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">
          CC
        </div>
        <div>
          <div className="font-semibold text-sm">Claim Cruncher</div>
          <div className="text-xs text-slate-400">Medical Billing</div>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navigation.map((item) => (
          <Link
            key={item.name}
            to={item.href}
            onClick={() => setSidebarOpen(false)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              isActive(item.href)
                ? 'bg-slate-700 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <item.icon className="w-5 h-5 shrink-0" />
            {item.name}
          </Link>
        ))}
      </nav>
      <div className="px-3 py-4 border-t border-slate-700">
        <div className="px-3 py-2 text-xs text-slate-500">
          Claim Cruncher v1.0
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 lg:hidden transform transition-transform duration-200 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="relative">
          <button
            onClick={() => setSidebarOpen(false)}
            className="absolute top-4 right-[-44px] p-2 text-white"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
          {sidebar}
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:shrink-0">{sidebar}</div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-4 sm:px-6 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-1.5 rounded-md text-slate-500 hover:bg-slate-100"
            >
              <Bars3Icon className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-semibold text-slate-800 hidden sm:block">
              {navigation.find((n) =>
                n.href === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(n.href)
              )?.name || 'Claim Cruncher'}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <>
                <div className="text-right hidden sm:block">
                  <div className="text-sm font-medium text-slate-700">
                    {user.full_name}
                  </div>
                  <span
                    className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${
                      roleBadgeColor[user.role] || 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {user.role.replace('_', ' ')}
                  </span>
                </div>
                <button
                  onClick={logout}
                  className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors"
                  title="Logout"
                >
                  <ArrowRightStartOnRectangleIcon className="w-5 h-5" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
