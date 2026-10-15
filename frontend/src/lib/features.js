// Switches for features that depend on something outside the app being ready.
// Vite bakes these in at build time, so change them in the host's environment
// settings (Vercel) and redeploy.

// "Forgot your password?" on the booker login sends a code by WhatsApp, which
// needs the Authentication message template — Meta only allows that once the
// business is verified. Turn on with VITE_PASSWORD_RESET_ENABLED=true once the
// `password_reset` template is approved. Until then the login page tells people
// to ask the office instead, which an admin does under Manage users.
export const PASSWORD_RESET_ENABLED = import.meta.env.VITE_PASSWORD_RESET_ENABLED === 'true';
