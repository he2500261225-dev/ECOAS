import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { clearSession, getToken, setSession } from '../api/client';
import type { User } from '../api/types';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem('ecoa_user');
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser);
  const [token, setToken] = useState<string | null>(getToken);
  const navigate = useNavigate();

  const logout = () => {
    clearSession();
    setUser(null);
    setToken(null);
    navigate('/login', { replace: true });
  };

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setToken(null);
      navigate('/login', { replace: true });
    };
    window.addEventListener('ecoa:unauthorized', onUnauthorized);
    return () => window.removeEventListener('ecoa:unauthorized', onUnauthorized);
  }, [navigate]);

  const login = async (username: string, password: string) => {
    const result = await api.login(username, password);
    setSession(result.token, result.user);
    setUser(result.user);
    setToken(result.token);
  };

  const value = useMemo(() => ({ user, token, login, logout }), [user, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function roleLabel(role?: string) {
  return role === 'manager' ? '运营主管' : '运营人员';
}
