"""
Per-app email templates for magic link sign-in.

Each app_id maps to branding (subject, sender name, HTML body).
To add a new app, add an entry to APP_TEMPLATES.
"""

APP_TEMPLATES = {
    "ai-oncologist-copilot": {
        "sender_name": "RISA OneView",
        "subject": "Sign in to RISA OneView",
        "body_html": """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;">
        <!-- Header -->
        <tr>
          <td style="background-color:#000000;padding:32px;text-align:center;">
            <span style="font-size:28px;font-weight:700;color:#ffffff;letter-spacing:0.05em;">RISA</span>
            <br>
            <span style="font-size:14px;color:#9ca3af;margin-top:4px;display:inline-block;">RISA OneView</span>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <h2 style="margin:0 0 16px;font-size:20px;color:#111;">Sign in to your account</h2>
            <p style="margin:0 0 24px;font-size:14px;color:#555;line-height:1.6;">
              Click the button below to securely sign in. This link expires in 1 hour and can only be used once.
            </p>
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr><td align="center">
                <a href="{link}" target="_blank"
                   style="display:inline-block;padding:14px 32px;background-color:#4b5563;color:#ffffff;
                          text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">
                  Sign In
                </a>
              </td></tr>
            </table>
            <p style="margin:24px 0 0;font-size:12px;color:#9ca3af;line-height:1.5;">
              If you didn't request this email, you can safely ignore it.<br>
              If the button doesn't work, copy and paste this link into your browser:<br>
              <a href="{link}" style="color:#6b7280;word-break:break-all;">{link}</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""",
    },
}

DEFAULT_APP_ID = "ai-oncologist-copilot"


def get_template(app_id: str | None = None) -> dict:
    """Return the template dict for the given app_id, falling back to the default."""
    return APP_TEMPLATES.get(app_id or DEFAULT_APP_ID, APP_TEMPLATES[DEFAULT_APP_ID])
