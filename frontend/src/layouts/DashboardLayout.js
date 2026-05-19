import React, { useState, useEffect, useCallback } from 'react';
import { NavLink, Outlet, useNavigate, Navigate } from 'react-router-dom';
import { useAuth, useToast } from '../contexts/AppContext';
import { Bot, MessageSquare, LayoutGrid, Megaphone, LogOut, Sparkles, BookOpen, Users, Settings, Power } from 'lucide-react';

const DashboardLayout = () => {
  const { user, logout, api, loading } = useAuth();
  const { success, error } = useToast();
  const navigate = useNavigate();
  const [aiActive, setAiActive] = useState(true);
  const [aiTogglingGlobal, setAiTogglingGlobal] = useState(false);

  const fetchAiStatus = useCallback(async () => {
    try {
      const res = await api.get('/chats/ai/global-status');
      setAiActive(res.data.ai_active);
    } catch (err) {
      // silent fail
    }
  }, [api]);

  useEffect(() => {
    if (user) fetchAiStatus();
  }, [user, fetchAiStatus]);

  const handleGlobalAiToggle = async () => {
    setAiTogglingGlobal(true);
    const newState = !aiActive;
    try {
      await api.put('/chats/ai/global-toggle', { is_paused: !newState });
      setAiActive(newState);
      success(newState ? '🤖 AI enabled for all chats' : '⏸ AI paused for all chats');
    } catch (err) {
      error('Failed to toggle AI');
    } finally {
      setAiTogglingGlobal(false);
    }
  };

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

  if (!user) return <Navigate to="/login" replace />;

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
    { path: '/dashboard/settings', icon: Settings, label: 'Settings' },
  ];

  const adminItems = [
    { path: '/dashboard/admin', icon: Users, label: 'User Management' },
  ];

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="dashboard-layout">
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
        <nav className="flex-1 py-6 px-3 overflow-y-auto">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-600 px-3 mb-4">Navigation</p>
          <ul className="space-y-1">
            {navItems.map(({ path, icon: Icon, label }) => (
              <li key={path}>
                <NavLink
                  to={path}
                  data-testid={`nav-${label.toLowerCase().replace(' ', '-')}`}
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

          {/* Super Admin Section */}
          {user?.role === 'super_admin' && (
            <>
              <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-600 px-3 mb-4 mt-6">Admin</p>
              <ul className="space-y-1">
                {adminItems.map(({ path, icon: Icon, label }) => (
                  <li key={path}>
                    <NavLink
                      to={path}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                          isActive
                            ? 'bg-white/5 text-white border-l-2 border-amber-400'
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
            </>
          )}
        </nav>

        {/* AI Badge */}
        <div className="px-3 mb-4">
          <div className="bg-gradient-to-r from-[#00E599]/10 to-[#00D4FF]/10 border border-[#00E599]/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-[#00E599]" />
              <span className="text-sm font-semibold text-[#00E599]">AI Powered</span>
            </div>
            <p className="text-xs text-zinc-400">
              {user?.business_name || 'Gemini'} — RAG Knowledge Active
            </p>
          </div>
        </div>

        {/* Global AI Toggle */}
        <div className="px-3 mb-3">
          <button
            onClick={handleGlobalAiToggle}
            disabled={aiTogglingGlobal}
            title={aiActive ? 'Click to pause AI for all chats' : 'Click to enable AI for all chats'}
            className={`w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all ${
              aiActive
                ? 'bg-[#00E599]/10 border-[#00E599]/30 hover:bg-[#00E599]/20'
                : 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20'
            } disabled:opacity-60 disabled:cursor-not-allowed`}
          >
            <div className="flex items-center gap-2">
              <Power className={`w-4 h-4 ${aiActive ? 'text-[#00E599]' : 'text-red-400'}`} />
              <div className="text-left">
                <p className={`text-xs font-semibold ${aiActive ? 'text-[#00E599]' : 'text-red-400'}`}>
                  AI {aiActive ? 'Active' : 'Paused'}
                </p>
                <p className="text-[10px] text-zinc-500">{aiActive ? 'Click to pause all' : 'Click to resume all'}</p>
              </div>
            </div>
            {/* Toggle pill */}
            <div className={`w-9 h-5 rounded-full transition-colors relative ${aiActive ? 'bg-[#00E599]' : 'bg-zinc-700'}`}>
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${aiActive ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </div>
          </button>
        </div>

        {/* User & Logout */}
        <div className="p-3 border-t border-white/5">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-[#111] flex items-center justify-center text-sm font-semibold">
              {user?.username?.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.username}</p>
              <p className="text-xs text-zinc-500 truncate">
                {user?.role === 'super_admin' ? '⭐ Super Admin' : user?.business_name || 'User'}
              </p>
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

      <main className="ml-[260px] min-h-screen">
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
