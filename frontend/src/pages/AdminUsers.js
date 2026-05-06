import React, { useState, useEffect, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { Navigate } from 'react-router-dom';
import { Users, Plus, Trash2, Edit2, X, Eye, EyeOff, CheckCircle2, AlertCircle, Phone } from 'lucide-react';

const AdminUsers = () => {
  const { user, api } = useAuth();
  const { success, error } = useToast();

  // ALL hooks must be declared before any early returns
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [showToken, setShowToken] = useState(false);
  const [form, setForm] = useState({
    username: '', password: '', business_name: '',
    meta_access_token: '', meta_phone_number_id: '', meta_verify_token: ''
  });
  const [isSaving, setIsSaving] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await api.get('/admin/users');
      setUsers(res.data);
    } catch (err) {
      error('Failed to load users');
    } finally {
      setIsLoading(false);
    }
  }, [api, error]);

  useEffect(() => {
    if (user?.role === 'super_admin') {
      fetchUsers();
    }
  }, [fetchUsers, user]);

  // Role guard AFTER all hooks
  if (!user) return null;
  if (user.role !== 'super_admin') return <Navigate to="/dashboard/inbox" replace />;

  const openCreate = () => {
    setEditingUser(null);
    setForm({ username: '', password: '', business_name: '', meta_access_token: '', meta_phone_number_id: '', meta_verify_token: '' });
    setShowModal(true);
  };

  const openEdit = (u) => {
    setEditingUser(u);
    setForm({ username: u.username, password: '', business_name: u.business_name || '', meta_access_token: '', meta_phone_number_id: u.meta_phone_number_id || '', meta_verify_token: '' });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (editingUser) {
        const payload = {};
        if (form.business_name) payload.business_name = form.business_name;
        if (form.meta_access_token) payload.meta_access_token = form.meta_access_token;
        if (form.meta_phone_number_id) payload.meta_phone_number_id = form.meta_phone_number_id;
        if (form.meta_verify_token) payload.meta_verify_token = form.meta_verify_token;
        if (form.password) payload.password = form.password;
        await api.put(`/admin/users/${editingUser.id}`, payload);
        success('User updated!');
      } else {
        await api.post('/admin/users', form);
        success('User created!');
      }
      setShowModal(false);
      fetchUsers();
    } catch (err) {
      error(err.response?.data?.detail || 'Failed to save user');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (userId, username) => {
    if (!window.confirm(`Delete user "${username}"? All their data will be permanently removed.`)) return;
    try {
      await api.delete(`/admin/users/${userId}`);
      success('User deleted');
      fetchUsers();
    } catch (err) {
      error(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  return (
    <div className="p-6 md:p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2 flex items-center gap-3">
            <Users className="w-8 h-8 text-amber-400" />
            User Management
          </h1>
          <p className="text-zinc-400">Manage tenant accounts — each user has their own WhatsApp number and knowledge base.</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 bg-[#00E599] text-black px-5 py-2.5 rounded-lg font-medium hover:bg-[#00E599]/90 transition-all">
          <Plus className="w-4 h-4" /> Add User
        </button>
      </div>

      {/* Table */}
      <div className="bg-[#111] border border-white/5 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-zinc-500">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">No users yet. Click "Add User" to create one.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5 text-xs font-bold uppercase tracking-wider text-zinc-500">
                <th className="px-6 py-4 text-left">User</th>
                <th className="px-6 py-4 text-left">Role</th>
                <th className="px-6 py-4 text-left">Phone Number ID</th>
                <th className="px-6 py-4 text-left">WhatsApp</th>
                <th className="px-6 py-4 text-left">Created</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-[#0A0A0A] border border-white/10 flex items-center justify-center text-sm font-semibold">
                        {u.username?.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-white">{u.username}</p>
                        <p className="text-xs text-zinc-500">{u.business_name || '—'}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${u.role === 'super_admin' ? 'bg-amber-400/10 text-amber-400' : 'bg-[#00E599]/10 text-[#00E599]'}`}>
                      {u.role === 'super_admin' ? '⭐ Super Admin' : 'User'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-mono text-xs text-zinc-400">{u.meta_phone_number_id || <span className="text-zinc-600 italic">not set</span>}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      {u.has_token ? (
                        <><CheckCircle2 className="w-4 h-4 text-[#00E599]" /><span className="text-xs text-[#00E599]">Connected</span></>
                      ) : (
                        <><AlertCircle className="w-4 h-4 text-amber-400" /><span className="text-xs text-amber-400">Not configured</span></>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-xs text-zinc-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 justify-end">
                      <button onClick={() => openEdit(u)}
                        className="p-2 text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-all">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      {u.role !== 'super_admin' && (
                        <button onClick={() => handleDelete(u.id, u.username)}
                          className="p-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/5 rounded-lg transition-all">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-lg">
            <div className="flex items-center justify-between p-6 border-b border-white/5">
              <h2 className="text-lg font-semibold">{editingUser ? `Edit: ${editingUser.username}` : 'Create New User'}</h2>
              <button onClick={() => setShowModal(false)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSave} className="p-6 space-y-4">
              {!editingUser && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Username *</label>
                    <input type="text" required value={form.username}
                      onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                      className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Password *</label>
                    <input type="password" required value={form.password}
                      onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                      className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm" />
                  </div>
                </div>
              )}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Business Name</label>
                <input type="text" value={form.business_name}
                  onChange={e => setForm(p => ({ ...p, business_name: e.target.value }))}
                  placeholder="My Restaurant"
                  className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 flex items-center gap-1"><Phone className="w-3 h-3" /> Phone Number ID</label>
                <input type="text" value={form.meta_phone_number_id}
                  onChange={e => setForm(p => ({ ...p, meta_phone_number_id: e.target.value }))}
                  placeholder="10774289021..."
                  className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm font-mono" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Access Token {editingUser && '(leave blank to keep)'}</label>
                <div className="relative">
                  <input type={showToken ? 'text' : 'password'} value={form.meta_access_token}
                    onChange={e => setForm(p => ({ ...p, meta_access_token: e.target.value }))}
                    placeholder="EAAW03LB0..."
                    className="w-full px-3 py-2.5 pr-10 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm font-mono" />
                  <button type="button" onClick={() => setShowToken(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
                    {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Webhook Verify Token</label>
                <input type="text" value={form.meta_verify_token}
                  onChange={e => setForm(p => ({ ...p, meta_verify_token: e.target.value }))}
                  placeholder="my-custom-verify-token"
                  className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm font-mono" />
              </div>
              {editingUser && (
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block">New Password (leave blank to keep)</label>
                  <input type="password" value={form.password}
                    onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-lg text-white focus:outline-none focus:border-[#00E599] text-sm" />
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2.5 border border-white/10 text-zinc-300 rounded-lg hover:bg-white/5 transition-all text-sm font-medium">
                  Cancel
                </button>
                <button type="submit" disabled={isSaving}
                  className="flex-1 px-4 py-2.5 bg-[#00E599] text-black rounded-lg font-medium hover:bg-[#00E599]/90 transition-all text-sm disabled:opacity-50">
                  {isSaving ? 'Saving...' : editingUser ? 'Update User' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminUsers;
