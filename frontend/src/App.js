import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, ToastProvider } from './contexts/AppContext';
import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';
import Inbox from './pages/Inbox';
import Templates from './pages/Templates';
import Campaigns from './pages/Campaigns';
import KnowledgeBase from './pages/KnowledgeBase';
import Settings from './pages/Settings';
import AdminUsers from './pages/AdminUsers';
import ToastContainer from './components/ToastContainer';
import './App.css';

function App() {
  return (
    <div className="App">
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/dashboard" element={<DashboardLayout />}>
                <Route index element={<Navigate to="/dashboard/inbox" replace />} />
                <Route path="inbox" element={<Inbox />} />
                <Route path="templates" element={<Templates />} />
                <Route path="campaigns" element={<Campaigns />} />
                <Route path="knowledge" element={<KnowledgeBase />} />
                <Route path="settings" element={<Settings />} />
                <Route path="admin" element={<AdminUsers />} />
              </Route>
              <Route path="/" element={<Navigate to="/login" replace />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </BrowserRouter>
          <ToastContainer />
        </AuthProvider>
      </ToastProvider>
    </div>
  );
}

export default App;
