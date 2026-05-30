import React, { useState, useEffect } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { Settings as SettingsIcon, Save, Eye, EyeOff, Phone, Key, Building2, Lock, CheckCircle2, AlertCircle, RefreshCw, Copy, Zap } from 'lucide-react';

const Settings = () => {
  const { user, api } = useAuth();
  const { success, error } = useToast();

  const [form, setForm] = useState({
    business_name: '',
    meta_access_token: '',
    meta_phone_number_id: '',
    meta_waba_id: '',
    meta_verify_token: '',
    password: '',
    confirm_password: '',
    shopify_store_url: '',
    shopify_api_token: '',
  });
  const [showToken, setShowToken] = useState(false);
  const [showShopifyToken, setShowShopifyToken] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [stats, setStats] = useState({ total_chunks: 0 });
  const [hasToken, setHasToken] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [settingsRes, statsRes] = await Promise.all([
          api.get('/settings'),
          api.get('/ai/knowledge/stats'),
        ]);
        const s = settingsRes.data;
        setForm(prev => ({
          ...prev,
          business_name: s.business_name || '',
          meta_phone_number_id: s.meta_phone_number_id || '',
          meta_waba_id: s.meta_waba_id || '',
          meta_verify_token: s.meta_verify_token || '',
          shopify_store_url: s.shopify_store_url || '',
          shopify_api_token: '', // never show API tokens
        }));
        setHasToken(s.has_token);
        setApiKey(s.api_key || '');
        setStats(statsRes.data);
      } catch (err) {
        console.error('Failed to load settings:', err);
      }
    };
    fetchSettings();
  }, [api]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (form.password && form.password !== form.confirm_password) {
      error('Passwords do not match');
      return;
    }
    setIsSaving(true);
    try {
      const payload = {};
      if (form.business_name) payload.business_name = form.business_name;
      if (form.meta_access_token) payload.meta_access_token = form.meta_access_token;
      if (form.meta_phone_number_id) payload.meta_phone_number_id = form.meta_phone_number_id;
      if (form.meta_waba_id) payload.meta_waba_id = form.meta_waba_id;
      if (form.meta_verify_token) payload.meta_verify_token = form.meta_verify_token;
      if (form.shopify_store_url) payload.shopify_store_url = form.shopify_store_url;
      if (form.shopify_api_token) payload.shopify_api_token = form.shopify_api_token;
      if (form.password) payload.password = form.password;
      await api.put('/settings', payload);
      success('Settings saved successfully!');
      setForm(prev => ({ ...prev, password: '', confirm_password: '', meta_access_token: '' }));
      if (form.meta_access_token) setHasToken(true);
    } catch (err) {
      error(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerateApiKey = async () => {
    setIsGenerating(true);
    try {
      const res = await api.post('/settings/generate-api-key');
      setApiKey(res.data.api_key);
      setShowApiKey(true);
      success('New API key generated!');
    } catch (err) {
      error('Failed to generate API key');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyApiKey = () => {
    navigator.clipboard.writeText(apiKey);
    success('API key copied to clipboard!');
  };

  const Field = ({ label, icon: Icon, children }) => (
    <div>
      <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-2">
        <Icon className="w-4 h-4 text-zinc-500" />
        {label}
      </label>
      {children}
    </div>
  );

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2 flex items-center gap-3">
          <SettingsIcon className="w-8 h-8 text-[#00E599]" />
          Settings
        </h1>
        <p className="text-zinc-400">Configure your WhatsApp business account and credentials.</p>
      </div>

      {/* Status Banner */}
      <div className={`flex items-center gap-3 p-4 rounded-xl mb-6 border ${hasToken ? 'bg-[#00E599]/5 border-[#00E599]/20 text-[#00E599]' : 'bg-amber-500/5 border-amber-500/20 text-amber-400'}`}>
        {hasToken ? <CheckCircle2 className="w-5 h-5 shrink-0" /> : <AlertCircle className="w-5 h-5 shrink-0" />}
        <div>
          <p className="font-medium text-sm">{hasToken ? 'WhatsApp Connected' : 'WhatsApp Not Configured'}</p>
          <p className="text-xs opacity-70">{hasToken ? `${stats.total_chunks} knowledge chunks active · Phone ID: ${form.meta_phone_number_id || 'not set'}` : 'Enter your Meta credentials below to start receiving messages.'}</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Business Info */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white mb-4">Business Information</h2>
          <Field label="Business Name" icon={Building2}>
            <input
              type="text"
              value={form.business_name}
              onChange={e => setForm(p => ({ ...p, business_name: e.target.value }))}
              placeholder="My Restaurant"
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors"
            />
          </Field>
        </div>

        {/* WhatsApp Credentials */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white mb-1">WhatsApp Credentials</h2>
          <p className="text-xs text-zinc-500 mb-4">Find these in your <span className="text-[#00E599]">Meta Developer Portal → WhatsApp → API Setup</span></p>

          <Field label="Phone Number ID" icon={Phone}>
            <input
              type="text"
              value={form.meta_phone_number_id}
              onChange={e => setForm(p => ({ ...p, meta_phone_number_id: e.target.value }))}
              placeholder="107742890211817..."
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
            />
          </Field>

          <Field label="WhatsApp Business Account ID (WABA ID)" icon={Phone}>
            <input
              type="text"
              value={form.meta_waba_id}
              onChange={e => setForm(p => ({ ...p, meta_waba_id: e.target.value }))}
              placeholder="135353879346191..."
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
            />
            <p className="text-xs text-zinc-600 mt-1.5">Required for template sync. Find it in Meta Dev Console → WhatsApp → API Setup → "WhatsApp Business Account ID".</p>
          </Field>

          <Field label="Access Token" icon={Key}>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={form.meta_access_token}
                onChange={e => setForm(p => ({ ...p, meta_access_token: e.target.value }))}
                placeholder={hasToken ? '••••••••••••• (leave blank to keep current)' : 'EAAW03LB0...'}
                className="w-full px-4 py-3 pr-12 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
              />
              <button type="button" onClick={() => setShowToken(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </Field>

          <Field label="Webhook Verify Token" icon={Key}>
            <input
              type="text"
              value={form.meta_verify_token}
              onChange={e => setForm(p => ({ ...p, meta_verify_token: e.target.value }))}
              placeholder="your-custom-verify-token"
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
            />
            <p className="text-xs text-zinc-600 mt-1.5">Set this exact value in Meta's webhook configuration → Verify Token field.</p>
          </Field>
        </div>

        {/* Shopify Credentials */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white mb-1">Shopify Integration</h2>
          <p className="text-xs text-zinc-500 mb-4">Required for fetching order details for order confirmation templates.</p>

          <Field label="Store URL" icon={Building2}>
            <input
              type="text"
              value={form.shopify_store_url}
              onChange={e => setForm(p => ({ ...p, shopify_store_url: e.target.value }))}
              placeholder="https://your-store.myshopify.com"
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
            />
          </Field>

          <Field label="Admin API Token" icon={Key}>
            <div className="relative">
              <input
                type={showShopifyToken ? 'text' : 'password'}
                value={form.shopify_api_token}
                onChange={e => setForm(p => ({ ...p, shopify_api_token: e.target.value }))}
                placeholder="shpat_..."
                className="w-full px-4 py-3 pr-12 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors font-mono text-sm"
              />
              <button type="button" onClick={() => setShowShopifyToken(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
                {showShopifyToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-zinc-600 mt-1.5">Needs "read_orders" permission.</p>
          </Field>
        </div>

        {/* Password */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white mb-4">Change Password</h2>
          <Field label="New Password" icon={Lock}>
            <input
              type="password"
              value={form.password}
              onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
              placeholder="Leave blank to keep current"
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors"
            />
          </Field>
          <Field label="Confirm New Password" icon={Lock}>
            <input
              type="password"
              value={form.confirm_password}
              onChange={e => setForm(p => ({ ...p, confirm_password: e.target.value }))}
              placeholder="Repeat new password"
              className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] transition-colors"
            />
          </Field>
        </div>

        {/* API Key */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#00E599]" />
              Integration API Key
            </h2>
            <button
              type="button"
              onClick={handleGenerateApiKey}
              disabled={isGenerating}
              className="flex items-center gap-2 px-3 py-1.5 text-xs bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20 rounded-lg hover:bg-[#00E599]/20 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${isGenerating ? 'animate-spin' : ''}`} />
              {apiKey ? 'Regenerate' : 'Generate Key'}
            </button>
          </div>
          <p className="text-xs text-zinc-500 mb-4">Permanent key for n8n, Zapier, or any automation — never expires, no JWT refresh needed.</p>
          {apiKey ? (
            <div className="space-y-3">
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  readOnly
                  className="w-full px-4 py-3 pr-20 bg-[#0A0A0A] border border-[#00E599]/20 rounded-lg text-[#00E599] font-mono text-xs focus:outline-none"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                  <button type="button" onClick={() => setShowApiKey(p => !p)}
                    className="p-1.5 text-zinc-500 hover:text-white rounded">
                    {showApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                  <button type="button" onClick={handleCopyApiKey}
                    className="p-1.5 text-zinc-500 hover:text-[#00E599] rounded">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="bg-[#0A0A0A] border border-white/5 rounded-lg p-3 space-y-1">
                <p className="text-xs text-zinc-500 font-medium mb-2">n8n HTTP Request — Headers:</p>
                <p className="text-xs font-mono"><span className="text-zinc-400">X-API-Key:</span> <span className="text-[#00E599]">{showApiKey ? apiKey : apiKey.slice(0,12) + '••••••'}</span></p>
              </div>
            </div>
          ) : (
            <div className="border border-dashed border-white/10 rounded-lg p-4 text-center">
              <p className="text-sm text-zinc-500">No API key yet — click "Generate Key" to create one.</p>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-2 bg-[#00E599] text-black px-6 py-2.5 rounded-lg font-medium hover:bg-[#00E599]/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Settings;
