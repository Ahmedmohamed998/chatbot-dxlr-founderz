import React, { useState, useEffect } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { BookOpen, Upload, Loader2, Sparkles, Trash2, Database } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const KnowledgeBase = () => {
  const { api } = useAuth();
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [stats, setStats] = useState({ total_chunks: 0 });
  const { success, error } = useToast();

  const fetchStats = async () => {
    try {
      const res = await api.get('/ai/knowledge/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  useEffect(() => { fetchStats(); }, []);

  const handleIngest = async (e) => {
    e.preventDefault();
    if (!content.trim()) { error('Please enter content to ingest'); return; }
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${BACKEND_URL}/api/ai/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text_content: content, metadata: { source: 'manual_input' } })
      });
      if (!response.ok) throw new Error('Failed to ingest knowledge');
      const data = await response.json();
      success(`Successfully ingested ${data.chunks_created} knowledge chunks!`);
      setContent('');
      fetchStats();
    } catch (err) {
      error(err.message || 'Failed to ingest knowledge');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Delete ALL your knowledge chunks? This cannot be undone.')) return;
    setIsClearing(true);
    try {
      const res = await api.delete('/ai/knowledge');
      success(`Deleted ${res.data.deleted} knowledge chunks`);
      fetchStats();
    } catch (err) {
      error('Failed to clear knowledge base');
    } finally {
      setIsClearing(false);
    }
  };

  return (
    <div className="p-6 md:p-8" data-testid="knowledge-page">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2 flex items-center gap-3">
            <BookOpen className="w-8 h-8 text-[#00E599]" />
            Knowledge Base
          </h1>
          <p className="text-zinc-400">Train your AI agent with your own business knowledge</p>
        </div>
        {/* Stats badge */}
        <div className="flex items-center gap-2 px-4 py-2 bg-[#00E599]/5 border border-[#00E599]/20 rounded-xl">
          <Database className="w-4 h-4 text-[#00E599]" />
          <span className="text-sm font-semibold text-[#00E599]">{stats.total_chunks} chunks stored</span>
        </div>
      </div>

      <div className="max-w-3xl space-y-6">
        {/* Ingest Form */}
        <div className="bg-[#111] border border-white/5 rounded-xl overflow-hidden">
          <div className="p-6 border-b border-white/5">
            <div className="flex items-center gap-3 mb-2">
              <Sparkles className="w-5 h-5 text-[#00E599]" />
              <h2 className="text-xl font-semibold">Ingest Knowledge</h2>
            </div>
            <p className="text-sm text-zinc-400">
              Paste text content below. The AI will chunk, embed, and store it in your private vector database to use when answering customer messages.
            </p>
          </div>
          <form onSubmit={handleIngest} className="p-6">
            <div className="mb-6">
              <label className="block text-sm font-medium text-zinc-300 mb-2">Knowledge Content</label>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                placeholder="Our business hours are Monday to Friday, 9AM to 5PM. We offer standard shipping which takes 3-5 business days..."
                className="w-full h-64 bg-[#0A0A0A] border border-white/10 rounded-lg p-4 text-white focus:outline-none focus:border-[#00E599] transition-colors resize-y"
                required
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmitting || !content.trim()}
                className="flex items-center gap-2 bg-[#00E599] text-black px-6 py-2.5 rounded-lg font-medium hover:bg-[#00E599]/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <><Loader2 className="w-5 h-5 animate-spin" />Processing...</>
                ) : (
                  <><Upload className="w-5 h-5" />Ingest to Vector DB</>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Danger Zone */}
        {stats.total_chunks > 0 && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-6">
            <h3 className="font-semibold text-red-400 mb-1">Danger Zone</h3>
            <p className="text-sm text-zinc-500 mb-4">Permanently delete all {stats.total_chunks} knowledge chunks from your account. The AI will lose all trained knowledge.</p>
            <button
              onClick={handleClear}
              disabled={isClearing}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-all text-sm font-medium disabled:opacity-50"
            >
              {isClearing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              {isClearing ? 'Clearing...' : 'Clear All Knowledge'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBase;
