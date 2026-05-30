import React, { useState, useRef } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import {
  Package, Send, Plus, Trash2, Upload, CheckCircle2,
  XCircle, Loader2, ShoppingBag, AlertCircle, ChevronDown
} from 'lucide-react';

const STATUS_COLORS = {
  idle:    'text-zinc-500',
  sending: 'text-amber-400',
  sent:    'text-[#00E599]',
  failed:  'text-red-400',
};

const StatusBadge = ({ status, error }) => {
  const icons = {
    idle:    null,
    sending: <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />,
    sent:    <CheckCircle2 className="w-3.5 h-3.5 text-[#00E599]" />,
    failed:  <XCircle className="w-3.5 h-3.5 text-red-400" />,
  };
  return (
    <div className="flex items-center gap-1.5 min-w-[90px]">
      {icons[status]}
      <span className={`text-xs font-medium ${STATUS_COLORS[status]}`}>
        {status === 'idle' ? '—' : status === 'sending' ? 'Sending...' : status === 'sent' ? 'Sent' : 'Failed'}
      </span>
      {status === 'failed' && error && (
        <span className="text-xs text-red-400 truncate max-w-[160px]" title={error}>({error})</span>
      )}
    </div>
  );
};

const TEMPLATE_OPTIONS = [
  { value: 'order_confirmation', label: 'order_confirmation (ar_EG)' },
];

const OrderConfirmations = () => {
  const { api } = useAuth();
  const { success, error, info } = useToast();

  const [rows, setRows] = useState([
    { id: 1, phone: '', order_number: '', status: 'idle', error: null, contact_name: null }
  ]);
  const [template, setTemplate] = useState('order_confirmation');
  const [isSending, setIsSending] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState('');
  const [summary, setSummary] = useState(null);
  const nextId = useRef(2);

  const addRow = () => {
    setRows(prev => [...prev, { id: nextId.current++, phone: '', order_number: '', status: 'idle', error: null, contact_name: null }]);
  };

  const removeRow = (id) => {
    setRows(prev => prev.filter(r => r.id !== id));
  };

  const updateRow = (id, field, value) => {
    setRows(prev => prev.map(r => r.id === id ? { ...r, [field]: value } : r));
  };

  const handleImport = () => {
    const lines = importText.trim().split('\n').filter(l => l.trim());
    const newRows = lines.map(line => {
      const parts = line.split(/[,\t]+/);
      return {
        id: nextId.current++,
        phone: (parts[0] || '').trim(),
        order_number: (parts[1] || '').trim(),
        status: 'idle',
        error: null,
        contact_name: null,
      };
    }).filter(r => r.phone);
    if (!newRows.length) { error('No valid rows found. Format: phone,order_number'); return; }
    setRows(prev => [...prev.filter(r => r.phone || r.order_number), ...newRows]);
    setImportText('');
    setShowImport(false);
    info(`Imported ${newRows.length} rows`);
  };

  const handleSendAll = async () => {
    const valid = rows.filter(r => r.phone.trim() && r.order_number.trim());
    if (!valid.length) { error('Add at least one phone + order number pair'); return; }

    setIsSending(true);
    setSummary(null);
    // Mark all as sending
    setRows(prev => prev.map(r =>
      r.phone && r.order_number ? { ...r, status: 'sending', error: null } : r
    ));

    try {
      const res = await api.post('/campaigns/order-confirmations', {
        template_name: template,
        items: valid.map(r => ({ phone: r.phone.trim(), order_number: r.order_number.trim() }))
      });

      const { results, sent, failed } = res.data;
      // Map results back to rows by phone+order
      setRows(prev => prev.map(r => {
        const match = results.find(
          res => res.phone === r.phone.trim() && res.order === r.order_number.trim().replace(/^#/, '')
        );
        if (!match) return r;
        return { ...r, status: match.status, error: match.error || null, contact_name: match.contact_name || null };
      }));

      setSummary({ sent, failed, total: results.length });
      if (failed === 0) success(`✅ All ${sent} messages sent and logged to Inbox!`);
      else error(`Sent ${sent}, failed ${failed}. Check the results below.`);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to send confirmations';
      error(msg);
      setRows(prev => prev.map(r => ({ ...r, status: r.status === 'sending' ? 'failed' : r.status, error: msg })));
    } finally {
      setIsSending(false);
    }
  };

  const handleClear = () => {
    setRows([{ id: nextId.current++, phone: '', order_number: '', status: 'idle', error: null, contact_name: null }]);
    setSummary(null);
  };

  const validCount = rows.filter(r => r.phone.trim() && r.order_number.trim()).length;

  return (
    <div className="p-6 md:p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2 flex items-center gap-3" style={{ fontFamily: 'Cabinet Grotesk' }}>
          <ShoppingBag className="w-8 h-8 text-[#00E599]" />
          Order Confirmations
        </h1>
        <p className="text-zinc-400">
          Enter phone numbers with their Shopify order numbers. We'll fetch order details automatically and send the confirmation template — each message will appear in the Inbox.
        </p>
      </div>

      {/* Template + Actions row */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-2 bg-[#111] border border-white/5 rounded-lg px-3 py-2">
          <Package className="w-4 h-4 text-zinc-400" />
          <span className="text-sm text-zinc-400 mr-1">Template:</span>
          <select
            value={template}
            onChange={e => setTemplate(e.target.value)}
            className="bg-transparent text-sm text-white focus:outline-none"
          >
            {TEMPLATE_OPTIONS.map(t => (
              <option key={t.value} value={t.value} style={{ background: '#111' }}>{t.label}</option>
            ))}
          </select>
        </div>

        <button
          onClick={() => setShowImport(p => !p)}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-[#111] border border-white/5 rounded-lg hover:bg-white/5 transition-colors"
        >
          <Upload className="w-4 h-4 text-zinc-400" />
          Import CSV
          <ChevronDown className={`w-3.5 h-3.5 text-zinc-500 transition-transform ${showImport ? 'rotate-180' : ''}`} />
        </button>

        <button
          onClick={addRow}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-[#111] border border-white/5 rounded-lg hover:bg-white/5 transition-colors"
        >
          <Plus className="w-4 h-4 text-zinc-400" />
          Add Row
        </button>

        <div className="flex-1" />

        <button
          onClick={handleClear}
          disabled={isSending}
          className="px-3 py-2 text-sm text-zinc-500 hover:text-white transition-colors disabled:opacity-40"
        >
          Clear All
        </button>

        <button
          onClick={handleSendAll}
          disabled={isSending || validCount === 0}
          className="flex items-center gap-2 px-5 py-2.5 bg-[#00E599] text-black text-sm font-semibold rounded-lg hover:bg-[#00CC88] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSending
            ? <><Loader2 className="w-4 h-4 animate-spin" />Sending...</>
            : <><Send className="w-4 h-4" />Send {validCount > 0 ? `(${validCount})` : 'All'}</>
          }
        </button>
      </div>

      {/* Import panel */}
      {showImport && (
        <div className="mb-5 bg-[#111] border border-white/5 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-2">
            Paste lines in format <code className="text-[#00E599] bg-[#0A0A0A] px-1 rounded">phone,order_number</code> — one per line. Phone must be international format without +.
          </p>
          <textarea
            rows={5}
            value={importText}
            onChange={e => setImportText(e.target.value)}
            placeholder={"201501234567,7940\n201509876543,7941\n201012345678,7942"}
            className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 rounded-lg text-sm font-mono text-zinc-300 focus:outline-none focus:border-[#00E599] resize-none"
          />
          <div className="flex justify-end gap-2 mt-2">
            <button onClick={() => setShowImport(false)} className="px-3 py-1.5 text-xs text-zinc-500 hover:text-white">Cancel</button>
            <button onClick={handleImport} className="px-4 py-1.5 text-xs bg-[#00E599] text-black rounded-lg font-medium hover:bg-[#00CC88]">Import</button>
          </div>
        </div>
      )}

      {/* Summary banner */}
      {summary && (
        <div className={`flex items-center gap-3 p-4 rounded-xl mb-5 border ${
          summary.failed === 0
            ? 'bg-[#00E599]/5 border-[#00E599]/20'
            : 'bg-amber-500/5 border-amber-500/20'
        }`}>
          {summary.failed === 0
            ? <CheckCircle2 className="w-5 h-5 text-[#00E599]" />
            : <AlertCircle className="w-5 h-5 text-amber-400" />
          }
          <div>
            <p className="font-medium text-sm">
              {summary.failed === 0
                ? `All ${summary.sent} messages sent successfully`
                : `${summary.sent} sent, ${summary.failed} failed`
              }
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">Messages have been logged to the Inbox</p>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#111] border border-white/5 rounded-xl overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_1fr_160px_36px] gap-3 px-4 py-3 border-b border-white/5 bg-black/30">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Phone Number</span>
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Order Number</span>
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Status</span>
          <span />
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/5">
          {rows.map((row) => (
            <div key={row.id} className="grid grid-cols-[1fr_1fr_160px_36px] gap-3 px-4 py-3 items-center">
              <input
                type="text"
                value={row.phone}
                onChange={e => updateRow(row.id, 'phone', e.target.value)}
                placeholder="201501234567"
                disabled={isSending}
                className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 rounded-lg text-sm font-mono focus:outline-none focus:border-[#00E599] disabled:opacity-50 transition-colors"
              />
              <input
                type="text"
                value={row.order_number}
                onChange={e => updateRow(row.id, 'order_number', e.target.value)}
                placeholder="7940 or #7940"
                disabled={isSending}
                className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 rounded-lg text-sm font-mono focus:outline-none focus:border-[#00E599] disabled:opacity-50 transition-colors"
              />
              <div className="flex flex-col">
                <StatusBadge status={row.status} error={row.error} />
                {row.contact_name && row.status === 'sent' && (
                  <span className="text-xs text-zinc-600 mt-0.5 truncate">{row.contact_name}</span>
                )}
              </div>
              <button
                onClick={() => removeRow(row.id)}
                disabled={isSending || rows.length === 1}
                className="p-1.5 text-zinc-600 hover:text-red-400 transition-colors disabled:opacity-30 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Footer add row */}
        <div className="px-4 py-3 border-t border-white/5 bg-black/20">
          <button
            onClick={addRow}
            disabled={isSending}
            className="flex items-center gap-2 text-sm text-zinc-500 hover:text-[#00E599] transition-colors disabled:opacity-40"
          >
            <Plus className="w-4 h-4" />
            Add another row
          </button>
        </div>
      </div>

      {/* Tips */}
      <div className="mt-6 bg-[#111] border border-white/5 rounded-xl p-5 space-y-2">
        <p className="text-xs font-semibold text-zinc-400 mb-3">📌 Notes</p>
        <p className="text-xs text-zinc-500">• Phone numbers must be in international format without + (e.g. <code className="text-zinc-300">201501234567</code>)</p>
        <p className="text-xs text-zinc-500">• Order numbers can include or omit the # prefix (both <code className="text-zinc-300">7940</code> and <code className="text-zinc-300">#7940</code> work)</p>
        <p className="text-xs text-zinc-500">• Each sent message is automatically logged to the Inbox and the customer's contact is saved with their name from Shopify</p>
        <p className="text-xs text-zinc-500">• AI is disabled by default for these contacts — enable it manually per contact in the Inbox if needed</p>
        <p className="text-xs text-zinc-500">• Make sure your Shopify credentials are set in <strong className="text-zinc-300">Settings → Shopify Integration</strong></p>
      </div>
    </div>
  );
};

export default OrderConfirmations;
