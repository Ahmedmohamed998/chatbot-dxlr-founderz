import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth, useToast } from '../contexts/AppContext';
import { Bot, Lock, User, Loader2 } from 'lucide-react';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, user } = useAuth();
  const { error, success } = useToast();
  const navigate = useNavigate();

  if (user) {
    return <Navigate to="/dashboard/inbox" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await login(username, password);
      success('Welcome back, Operator');
      navigate('/dashboard/inbox');
    } catch (err) {
      error(err.response?.data?.detail || 'Invalid credentials');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left side - Background */}
      <div 
        className="hidden lg:flex lg:w-1/2 relative items-center justify-center"
        style={{
          backgroundImage: 'url(https://static.prod-images.emergentagent.com/jobs/7d7e878c-a0a3-42af-922c-67ade2252a16/images/e3468a1f5330336964fe5bed4c578211a031df64c6eddeb6a4e594fedf5353a2.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative z-10 text-center px-8">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-[#00E599] flex items-center justify-center">
              <Bot className="w-7 h-7 text-black" />
            </div>
            <h1 className="text-4xl font-black tracking-tighter text-white" style={{ fontFamily: 'Cabinet Grotesk' }}>
              WhatsBot
            </h1>
          </div>
          <p className="text-lg text-zinc-300 max-w-md">
            AI-powered WhatsApp automation platform for modern businesses
          </p>
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-[#0A0A0A]">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-12">
            <div className="w-10 h-10 rounded-xl bg-[#00E599] flex items-center justify-center">
              <Bot className="w-6 h-6 text-black" />
            </div>
            <h1 className="text-2xl font-black tracking-tighter" style={{ fontFamily: 'Cabinet Grotesk' }}>
              WhatsBot
            </h1>
          </div>

          <div className="mb-8">
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-2">
              Control Panel
            </p>
            <h2 className="text-3xl font-bold tracking-tight" style={{ fontFamily: 'Cabinet Grotesk' }}>
              Welcome back, Operator
            </h2>
            <p className="text-zinc-400 mt-2">
              Enter your credentials to access the dashboard
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Username</label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input
                  data-testid="login-username-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className="w-full pl-12 pr-4 py-3 bg-[#111] border border-white/5 rounded-lg focus:border-[#00E599] focus:ring-1 focus:ring-[#00E599] transition-all"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input
                  data-testid="login-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full pl-12 pr-4 py-3 bg-[#111] border border-white/5 rounded-lg focus:border-[#00E599] focus:ring-1 focus:ring-[#00E599] transition-all"
                  required
                />
              </div>
            </div>

            <button
              data-testid="login-submit-button"
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-[#00E599] hover:bg-[#00CC88] text-black font-semibold rounded-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Authenticating...
                </>
              ) : (
                'Access Dashboard'
              )}
            </button>
          </form>

          <p className="text-center text-zinc-500 text-sm mt-8">
            Default credentials: admin / Admin123!
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
