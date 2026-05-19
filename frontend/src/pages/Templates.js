import React, { useState, useEffect, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { LayoutGrid, Globe, CheckCircle, Clock, XCircle, Loader2, RefreshCw, Plus, X } from 'lucide-react';

const TemplateSkeleton = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    {[...Array(6)].map((_, i) => (
      <div key={i} className="bg-[#111] border border-white/5 rounded-xl p-6">
        <div className="h-5 w-2/3 skeleton rounded mb-4" />
        <div className="h-4 w-1/2 skeleton rounded mb-6" />
        <div className="space-y-2">
          <div className="h-3 w-full skeleton rounded" />
          <div className="h-3 w-4/5 skeleton rounded" />
        </div>
        <div className="flex gap-2 mt-6">
          <div className="h-6 w-20 skeleton rounded-full" />
          <div className="h-6 w-16 skeleton rounded-full" />
        </div>
      </div>
    ))}
  </div>
);

const CATEGORIES = ['MARKETING', 'UTILITY', 'AUTHENTICATION'];
const LANGUAGES = [
  { code: 'ar', label: 'Arabic (ar)' },
  { code: 'en_US', label: 'English (en_US)' },
  { code: 'en', label: 'English (en)' },
  { code: 'fr', label: 'French (fr)' },
  { code: 'es', label: 'Spanish (es)' },
];

const Templates = () => {
  const { api } = useAuth();
  const { success, error } = useToast();

  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState({
    name: '',
    category: 'MARKETING',
    language: 'ar',
    body: '',
  });

  const fetchTemplates = useCallback(async (showRefresh = false) => {
    if (showRefresh) setIsRefreshing(true);
    try {
      const response = await api.get('/templates');
      setTemplates(response.data);
      if (showRefresh) success('Templates refreshed');
    } catch (err) {
      console.error('Failed to fetch templates:', err);
      error('Failed to load templates');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [api, success, error]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.body.trim()) {
      error('Template name and body are required');
      return;
    }
    setIsCreating(true);
    try {
      await api.post('/templates', {
        name: form.name.trim().toLowerCase().replace(/\s+/g, '_'),
        category: form.category,
        language: form.language,
        components: [
          { type: 'BODY', text: form.body.trim() }
        ],
      });
      success('Template created! It may take a few minutes for Meta to approve it.');
      setShowModal(false);
      setForm({ name: '', category: 'MARKETING', language: 'ar', body: '' });
      fetchTemplates();
    } catch (err) {
      error(err.response?.data?.detail || 'Failed to create template');
    } finally {
      setIsCreating(false);
    }
  };

  const getStatusBadge = (status) => {
    const s = status?.toLowerCase() || 'unknown';
    if (s === 'approved' || s === 'active' || s === 'active - quality_score_unknown')
      return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-approved rounded-full"><CheckCircle className="w-3 h-3" />Approved</span>;
    if (s === 'pending' || s === 'submitted')
      return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-pending rounded-full"><Clock className="w-3 h-3" />Pending</span>;
    if (s === 'rejected' || s === 'disabled')
      return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-rejected rounded-full"><XCircle className="w-3 h-3" />Rejected</span>;
    return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-zinc-800 text-zinc-400 rounded-full">{status || 'Unknown'}</span>;
  };

  const getCategoryBadge = (category) => {
    const colors = {
      MARKETING: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      UTILITY: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      AUTHENTICATION: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border ${colors[category?.toUpperCase()] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'}`}>
        {category || 'Other'}
      </span>
    );
  };

  const getTemplatePreview = (components) => {
    if (!components || !Array.isArray(components)) return 'No preview available';
    const body = components.find(c => c.type === 'BODY' || c.type === 'body');
    if (body?.text) return body.text.length > 120 ? body.text.substring(0, 120) + '...' : body.text;
    return 'No preview available';
  };

  return (
    <div className="p-6 md:p-8" data-testid="templates-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ fontFamily: 'Cabinet Grotesk' }}>Message Templates</h1>
          <p className="text-zinc-400">Manage your WhatsApp approved message templates</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchTemplates(true)}
            disabled={isRefreshing}
            data-testid="refresh-templates-button"
            className="flex items-center gap-2 px-4 py-2.5 bg-[#111] border border-white/5 rounded-lg hover:border-white/20 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Sync from Meta</span>
          </button>
          <button
            data-testid="create-template-button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#00E599] text-black font-semibold rounded-lg hover:bg-[#00CC88] transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Create Template</span>
          </button>
        </div>
      </div>

      {/* Templates Grid */}
      {isLoading ? (
        <TemplateSkeleton />
      ) : templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-20 h-20 rounded-2xl bg-[#111] border border-white/5 flex items-center justify-center mb-6">
            <LayoutGrid className="w-10 h-10 text-zinc-600" />
          </div>
          <h2 className="text-2xl font-bold mb-2">No templates found</h2>
          <p className="text-zinc-500 max-w-md mb-6">Connect your Meta Business account or create templates to see them here</p>
          <button onClick={() => fetchTemplates(true)} className="flex items-center gap-2 px-4 py-2.5 bg-[#00E599] text-black font-semibold rounded-lg hover:bg-[#00CC88] transition-all">
            <RefreshCw className="w-4 h-4" /><span>Sync Templates</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div key={template.id} data-testid={`template-card-${template.id}`}
              className="bg-[#111] border border-white/5 rounded-xl p-6 hover:border-white/20 transition-all hover:-translate-y-[1px]">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg mb-1">{template.name}</h3>
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <Globe className="w-3.5 h-3.5" />
                    <span className="uppercase">{template.language || 'EN'}</span>
                  </div>
                </div>
                {getStatusBadge(template.status)}
              </div>
              <div className="bg-[#0A0A0A] border border-white/5 rounded-lg p-4 mb-4">
                <p className="text-sm text-zinc-400 leading-relaxed">{getTemplatePreview(template.components)}</p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">{getCategoryBadge(template.category)}</div>
                {template.meta_template_id && (
                  <span className="text-xs text-zinc-600 font-mono">ID: {template.meta_template_id.slice(-8)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Template Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-lg">
            <div className="flex items-center justify-between p-6 border-b border-white/5">
              <h2 className="text-lg font-semibold">Create New Template</h2>
              <button onClick={() => setShowModal(false)} className="text-zinc-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Template Name *</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="welcome_message"
                  className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm font-mono"
                />
                <p className="text-xs text-zinc-600 mt-1">Lowercase letters, numbers and underscores only. Spaces will be converted to underscores.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block">Category *</label>
                  <select
                    value={form.category}
                    onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm"
                  >
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block">Language *</label>
                  <select
                    value={form.language}
                    onChange={e => setForm(p => ({ ...p, language: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm"
                  >
                    {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Message Body *</label>
                <textarea
                  required
                  rows={5}
                  value={form.body}
                  onChange={e => setForm(p => ({ ...p, body: e.target.value }))}
                  placeholder="Hello {{1}}, welcome to our service! How can we help you today?"
                  className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm resize-none"
                />
                <p className="text-xs text-zinc-600 mt-1">Use {'{{1}}'}, {'{{2}}'} for dynamic variables. Template must be approved by Meta before use.</p>
              </div>

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2.5 border border-white/10 text-zinc-300 rounded-lg hover:bg-white/5 transition-all text-sm font-medium">
                  Cancel
                </button>
                <button type="submit" disabled={isCreating}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-[#00E599] text-black rounded-lg font-medium hover:bg-[#00CC88] transition-all text-sm disabled:opacity-50">
                  {isCreating ? <><Loader2 className="w-4 h-4 animate-spin" />Creating...</> : <><Plus className="w-4 h-4" />Create Template</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Templates;
