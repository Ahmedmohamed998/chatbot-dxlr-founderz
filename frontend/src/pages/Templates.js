import React, { useState, useEffect, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { LayoutGrid, Globe, CheckCircle, Clock, XCircle, Loader2, RefreshCw, Plus } from 'lucide-react';

// Skeleton Loader
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

const Templates = () => {
  const { api } = useAuth();
  const { success, error } = useToast();
  
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const getStatusBadge = (status) => {
    const statusLower = status?.toLowerCase() || 'unknown';
    
    if (statusLower === 'approved' || statusLower === 'active') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-approved rounded-full">
          <CheckCircle className="w-3 h-3" />
          Approved
        </span>
      );
    }
    
    if (statusLower === 'pending' || statusLower === 'submitted') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-pending rounded-full">
          <Clock className="w-3 h-3" />
          Pending
        </span>
      );
    }
    
    if (statusLower === 'rejected' || statusLower === 'disabled') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium badge-rejected rounded-full">
          <XCircle className="w-3 h-3" />
          Rejected
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-zinc-800 text-zinc-400 rounded-full">
        {status || 'Unknown'}
      </span>
    );
  };

  const getCategoryBadge = (category) => {
    const categoryUpper = category?.toUpperCase() || 'OTHER';
    const colors = {
      MARKETING: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      UTILITY: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      AUTHENTICATION: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      OTHER: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    };
    
    return (
      <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border ${colors[categoryUpper] || colors.OTHER}`}>
        {category || 'Other'}
      </span>
    );
  };

  const getTemplatePreview = (components) => {
    if (!components || !Array.isArray(components)) return 'No preview available';
    
    const bodyComponent = components.find(c => c.type === 'BODY' || c.type === 'body');
    if (bodyComponent?.text) {
      return bodyComponent.text.length > 120 
        ? bodyComponent.text.substring(0, 120) + '...'
        : bodyComponent.text;
    }
    
    return 'No preview available';
  };

  return (
    <div className="p-6 md:p-8" data-testid="templates-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ fontFamily: 'Cabinet Grotesk' }}>
            Message Templates
          </h1>
          <p className="text-zinc-400">
            Manage your WhatsApp approved message templates
          </p>
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
          <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk' }}>
            No templates found
          </h2>
          <p className="text-zinc-500 max-w-md mb-6">
            Connect your Meta Business account or create templates to see them here
          </p>
          <button
            onClick={() => fetchTemplates(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#00E599] text-black font-semibold rounded-lg hover:bg-[#00CC88] transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Sync Templates</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div
              key={template.id}
              data-testid={`template-card-${template.id}`}
              className="bg-[#111] border border-white/5 rounded-xl p-6 hover:border-white/20 transition-all hover:-translate-y-[1px]"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg mb-1" style={{ fontFamily: 'Cabinet Grotesk' }}>
                    {template.name}
                  </h3>
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <Globe className="w-3.5 h-3.5" />
                    <span className="uppercase">{template.language || 'EN'}</span>
                  </div>
                </div>
                {getStatusBadge(template.status)}
              </div>

              {/* Preview */}
              <div className="bg-[#0A0A0A] border border-white/5 rounded-lg p-4 mb-4">
                <p className="text-sm text-zinc-400 leading-relaxed">
                  {getTemplatePreview(template.components)}
                </p>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getCategoryBadge(template.category)}
                </div>
                {template.meta_template_id && (
                  <span className="text-xs text-zinc-600 font-mono">
                    ID: {template.meta_template_id.slice(-8)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Templates;
