import React from 'react';
import { NavLink, Outlet, useNavigate, Navigate } from 'react-router-dom';
import { useAuth, useToast } from '../contexts/AppContext';
import { Bot, MessageSquare, LayoutGrid, Megaphone, LogOut, Sparkles, BookOpen } from 'lucide-react';

const DashboardLayout = () => {
  const { user, logout, loading } = useAuth();
  const { success } = useToast();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#00E599] border-t-transparent rounded-full animate-spin" />
          <span className="text-zinc-400">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = () => {
    logout();
    success('Logged out successfully');
    navigate('/login');
  };

  const navItems = [
    { path: '/dashboard/inbox', icon: MessageSquare, label: 'Inbox' },
    { path: '/dashboard/templates', icon: LayoutGrid, label: 'Templates' },
    { path: '/dashboard/campaigns', icon: Megaphone, label: 'Campaigns' },
    { path: '/dashboard/knowledge', icon: BookOpen, label: 'Knowledge Base' },
  ];

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="dashboard-layout">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-screen w-[260px] bg-[#050505] border-r border-white/5 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-white/5">
          <div className="w-9 h-9 rounded-lg bg-[#00E599] flex items-center justify-center">
            <Bot className="w-5 h-5 text-black" />
          </div>
          <span className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Cabinet Grotesk' }}>
            WhatsBot
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-6 px-3">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-600 px-3 mb-4">
            Navigation
          </p>
          <ul className="space-y-1">
            {navItems.map(({ path, icon: Icon, label }) => (
              <li key={path}>
                <NavLink
                  to={path}
                  data-testid={`nav-${label.toLowerCase()}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                      isActive
                        ? 'bg-white/5 text-white border-l-2 border-[#00E599]'
                        : 'text-zinc-400 hover:text-white hover:bg-white/5'
                    }`
                  }
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* AI Badge */}
        <div className="px-3 mb-4">
          <div className="bg-gradient-to-r from-[#00E599]/10 to-[#00D4FF]/10 border border-[#00E599]/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-[#00E599]" />
              <span className="text-sm font-semibold text-[#00E599]">AI Powered</span>
            </div>
            <p className="text-xs text-zinc-400">
              Gemini 3 Flash handles customer conversations automatically
            </p>
          </div>
        </div>

        {/* User & Logout */}
        <div className="p-3 border-t border-white/5">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-[#111] flex items-center justify-center text-sm font-semibold">
              {user.username?.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user.username}</p>
              <p className="text-xs text-zinc-500">Administrator</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-button"
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
          >
            <LogOut className="w-5 h-5" />
            <span className="font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-[260px] min-h-screen">
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
