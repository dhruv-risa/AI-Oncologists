import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import risaLogo from '../assets/risa-logo.svg';

export default function LoginPage() {
  const { sendMagicLink, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [validationError, setValidationError] = useState('');

  const validateEmail = (value: string) => {
    if (!value.trim()) return 'Please enter a valid email address';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Please enter a valid email address';
    return '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateEmail(email);
    if (err) { setValidationError(err); return; }
    setValidationError('');
    setSending(true);
    clearError();
    const success = await sendMagicLink(email.trim());
    setSending(false);
    if (success) setSent(true);
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#ffffff',
      padding: '2rem',
    }}>
      {/* Logo */}
      <img src={risaLogo} alt="RISA" style={{ width: '160px', marginBottom: '0.5rem' }} />
      <p style={{ fontSize: '1rem', fontWeight: 500, color: '#111111', marginBottom: '2rem' }}>RISA OneView</p>

      {/* Card */}
      <div style={{
        width: '100%',
        maxWidth: '420px',
        backgroundColor: '#ffffff',
        border: '1px solid #111111',
        borderRadius: '12px',
        padding: '2.5rem 2rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.12)',
      }}>
        {sent ? (
          <div style={{ textAlign: 'center' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#111111', marginBottom: '1rem' }}>Check your email</h2>
            <p style={{ fontSize: '0.875rem', color: '#555555', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              We sent a sign-in link to <span style={{ color: '#111111', fontWeight: 600 }}>{email}</span>. Click the link in the email to sign in.
            </p>
            <p style={{ fontSize: '0.75rem', color: '#666666', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              Don't see it? Check your spam folder. The link expires in 1 hour.
            </p>
            <button
              onClick={() => { setSent(false); clearError(); setValidationError(''); }}
              style={{
                marginTop: '0.5rem',
                fontSize: '0.875rem',
                color: '#888888',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Use a different email
            </button>
          </div>
        ) : (
          <>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#111111', textAlign: 'center', marginBottom: '1.5rem' }}>
              Welcome!
            </h2>
            <form onSubmit={handleSubmit}>
              <label htmlFor="email" style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#333333', marginBottom: '0.5rem' }}>
                Email Address <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setValidationError(''); }}
                disabled={sending}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  backgroundColor: '#ffffff',
                  color: '#111111',
                  border: validationError || error ? '2px solid #ef4444' : '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '0.875rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />

              {validationError && (
                <p style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.5rem' }}>{validationError}</p>
              )}

              {error && (
                <p style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '0.5rem' }}>{error}</p>
              )}

              <button
                type="submit"
                disabled={sending}
                style={{
                  width: '100%',
                  marginTop: '1.5rem',
                  padding: '0.75rem',
                  backgroundColor: '#111111',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  cursor: sending ? 'not-allowed' : 'pointer',
                  opacity: sending ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                }}
              >
                {sending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  'Send Link'
                )}
              </button>
            </form>
          </>
        )}
      </div>

      {/* Footer */}
      <div style={{ marginTop: '3rem', textAlign: 'center' }}>
        <p style={{ fontSize: '0.875rem', fontWeight: 500, color: '#111111' }}>Need Help? Contact Us</p>
        <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Version : 1.0.0</p>
      </div>
    </div>
  );
}
