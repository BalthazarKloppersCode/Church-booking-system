import { useEffect, useState } from 'react';
import { api } from '../lib/api';

const RESEND_SECONDS = 60;

// "Forgot your password?" for bookers. Step 1: their email — a 6-digit code goes
// to the WhatsApp number saved on the account (the same reply is shown whether or
// not the email is registered). Step 2: the code and a new password.
export default function ForgotPassword({ initialEmail = '', onBack, onDone }) {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);

  // Count down before "send again" is offered (the server enforces its own limit too).
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  async function sendCode(e) {
    e?.preventDefault();
    setError('');
    setBusy(true);
    try {
      const result = await api.forgotPassword(email.trim());
      setMessage(result.message);
      setStep('code');
      setWait(RESEND_SECONDS);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveNewPassword(e) {
    e.preventDefault();
    setError('');
    if (password.length < 8) return setError('Choose a password of at least 8 characters.');
    if (password !== confirm) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      await api.resetPassword(email.trim(), code.trim(), password);
      onDone(email.trim());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ fontSize: 18, margin: '0 0 6px' }}>Reset your password</h2>

      {error && <p role="alert" style={{ color: 'var(--no)', fontSize: 13, margin: '0 0 10px' }}>{error}</p>}

      {step === 'email' ? (
        <form onSubmit={sendCode}>
          <p style={{ fontSize: 14, margin: '0 0 14px' }}>
            Enter the email on your account. We'll send a 6-digit code to the WhatsApp number saved on it.
          </p>
          <div className="field">
            <label>Email</label>
            <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Sending…' : 'Send me a code'}</button>
        </form>
      ) : (
        <form onSubmit={saveNewPassword}>
          <p role="status" style={{ fontSize: 14, margin: '0 0 14px' }}>{message}</p>
          <div className="field">
            <label>6-digit code</label>
            <input
              required
              autoFocus
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              pattern="\d{6}"
              title="The 6 digits from your WhatsApp message"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
          </div>
          <div className="field">
            <label>New password</label>
            <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <span className="field-hint">At least 8 characters.</span>
          </div>
          <div className="field">
            <label>Type it again</label>
            <input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Saving…' : 'Set new password'}</button>
          <p style={{ fontSize: 13, color: 'var(--ink-2)', margin: '12px 0 0' }}>
            No message after a minute?{' '}
            <button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, height: 'auto', textDecoration: 'underline' }} disabled={wait > 0 || busy} onClick={sendCode}>
              {wait > 0 ? `Send again in ${wait}s` : 'Send again'}
            </button>
            {' '}The code lasts 15 minutes. If it never comes, the number on your account may be out of date — ask the admin office to reset it for you.
          </p>
        </form>
      )}

      <p style={{ margin: '14px 0 0', fontSize: 13 }}>
        <button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, height: 'auto' }} onClick={onBack}>← Back to log in</button>
      </p>
    </div>
  );
}
