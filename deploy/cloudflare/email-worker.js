export default {
  async email(message, env, ctx) {
    // URL til din Peng backend webhook
    const webhookUrl = env.PENG_WEBHOOK_URL || "https://peng.seame.click/api/inbound/email";

    try {
      // Hent hele den rå MIME/RFC822 e-mail stream
      const rawEmail = await new Response(message.raw).arrayBuffer();

      // Videresend til Peng webhook
      const response = await fetch(webhookUrl, {
        method: "POST",
        headers: {
          "Content-Type": "message/rfc822",
          "X-Inbound-From": message.from,
          "X-Inbound-To": message.to,
        },
        body: rawEmail,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Peng Inbound] Fejl fra backend (${response.status}): ${errorText}`);
      } else {
        const data = await response.json();
        console.log(`[Peng Inbound] Kvitteringer behandlet for ${message.to}:`, data);
      }
    } catch (err) {
      console.error(`[Peng Inbound] Netværksfejl under videresendelse:`, err);
    }
  },
};
