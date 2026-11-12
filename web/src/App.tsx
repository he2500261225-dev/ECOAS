import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth } from './auth/AuthContext';
import { AppLayout } from './layout/AppLayout';
import { Dashboard } from './pages/Dashboard';
import { ImportCenter } from './pages/ImportCenter';
import { Login } from './pages/Login';
import { ProductDetail } from './pages/ProductDetail';
import { Settings } from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/products/:id" element={<ProductDetail />} />
        <Route path="/import" element={<ImportCenter />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
