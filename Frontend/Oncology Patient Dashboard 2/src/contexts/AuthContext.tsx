import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  onAuthStateChanged,
  isSignInWithEmailLink,
  signInWithEmailLink,
  signOut as firebaseSignOut,
  User,
} from 'firebase/auth';
import { auth } from '../lib/firebase';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface AuthContextState {
  user: User | null;
  loading: boolean;
  error: string | null;
  sendMagicLink: (email: string) => Promise<boolean>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextState | undefined>(undefined);

const EMAIL_STORAGE_KEY = 'emailForSignIn';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Handle magic link callback on mount
  useEffect(() => {
    if (isSignInWithEmailLink(auth, window.location.href)) {
      let email = window.localStorage.getItem(EMAIL_STORAGE_KEY);
      if (!email) {
        email = window.prompt('Please provide your email for confirmation');
      }
      if (email) {
        setLoading(true);
        signInWithEmailLink(auth, email, window.location.href)
          .then(() => {
            window.localStorage.removeItem(EMAIL_STORAGE_KEY);
            // Clean up the URL
            window.history.replaceState(null, '', window.location.pathname);
          })
          .catch((err) => {
            console.error('Error signing in with email link:', err);
            setError('Failed to sign in. The link may have expired. Please request a new one.');
            setLoading(false);
          });
      }
    }
  }, []);

  // Listen to auth state changes
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const sendMagicLink = useCallback(async (email: string): Promise<boolean> => {
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/send-magic-link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Failed to send sign-in link. Please try again.');
        return false;
      }

      if (!data.success) {
        setError(data.error || 'Failed to send sign-in link. Please try again.');
        return false;
      }

      // Store email for sign-in completion when user clicks the link
      window.localStorage.setItem(EMAIL_STORAGE_KEY, email);
      return true;
    } catch (err) {
      console.error('Error sending magic link:', err);
      setError('Failed to send sign-in link. Please try again.');
      return false;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await firebaseSignOut(auth);
    } catch (err) {
      console.error('Error signing out:', err);
    }
  }, []);

  const clearError = useCallback(() => { setError(null); }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, sendMagicLink, signOut, clearError }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextState => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
