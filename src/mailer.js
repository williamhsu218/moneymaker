// Sends transactional email through Resend (https://resend.com) when
// RESEND_API_KEY is set; otherwise prints the email to the server log so
// password resets still work during local development.

export function createMailer(config) {
  const enabled = Boolean(config.resendApiKey && config.emailFrom);

  return {
    enabled,
    async send({ to, subject, text }) {
      if (!enabled) {
        console.log(`[mailer] (not configured) To: ${to}\nSubject: ${subject}\n\n${text}\n`);
        return;
      }
      const res = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${config.resendApiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ from: config.emailFrom, to: [to], subject, text }),
      });
      if (!res.ok) {
        throw new Error(`Resend error ${res.status}: ${await res.text()}`);
      }
    },
  };
}
