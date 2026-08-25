# Opsætning af Cloudflare Email Routing & Worker til Peng

Denne guide viser, hvordan du opsætter gratis automatisk videresendelse af Storebox/Nexi kvitteringsmails via **Cloudflare Email Routing** og en **Cloudflare Email Worker**.

---

## 1. Konfiguration i Peng (`.env`)

For at Peng kan generere den korrekte e-mailadresse i brugerfladen under *Indstillinger*, tilføjes følgende til din `.env` eller `docker-compose.yml`:

```ini
# Dit domæne der er tilknyttet Cloudflare
INBOUND_EMAIL_DOMAIN=ditdomaene.dk

# Præfiks til plus-addressing (standard: receipts)
INBOUND_EMAIL_PREFIX=receipts
```

Hver husstand får herefter vist en adresse i formatet:
`receipts+<husstands_token>@ditdomaene.dk`

---

## 2. Aktivér Cloudflare Email Routing

1. Log ind på dit [Cloudflare Dashboard](https://dash.cloudflare.com/) og vælg dit domæne.
2. Gå til **Email Routing** i venstremenuen.
3. Klik på **Get Started** / **Enable Email Routing**.
4. Følg Cloudflares automatiske DNS-guide (den tilføjer de nødvendige `MX` og `TXT` (SPF) records på dit domæne).

---

## 3. Opret Cloudflare Email Worker

### Mulighed A: Direkte i Cloudflare Dashboard
1. Gå til **Workers & Pages** -> **Create application** -> **Create Worker**.
2. Giv den et navn (f.eks. `peng-email-inbound`).
3. Klik på **Deploy**, og derefter **Edit code**.
4. Erstat koden med følgende:

```javascript
export default {
  async email(message, env, ctx) {
    const webhookUrl = env.PENG_WEBHOOK_URL || "https://peng.ditdomaene.dk/api/inbound/email";

    try {
      // Hent hele den rå MIME e-mail stream
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
        console.error(`[Peng] Webhook fejl (${response.status}): ${errorText}`);
      } else {
        const data = await response.json();
        console.log(`[Peng] Modtaget og behandlet:`, data);
      }
    } catch (err) {
      console.error(`[Peng] Netværksfejl under videresendelse:`, err);
    }
  },
};
```

5. Gå til Workerens **Settings** -> **Variables and Secrets** og tilføj:
   - Variabel: `PENG_WEBHOOK_URL`
   - Værdi: `https://peng.ditdomaene.dk/api/inbound/email` (erstat med din rigtige Peng-adresse)

### Mulighed B: Via Wrangler CLI
Hvis du bruger Wrangler lokalt:
```bash
cd deploy/cloudflare
# Ret URL i wrangler.toml
npx wrangler deploy
```

---

## 4. Opret Routing-regel i Cloudflare

1. Gå tilbage til **Email Routing** under dit domæne.
2. Vælg fanen **Routing Rules**.
3. Under **Catch-all rule** eller **Custom addresses**:
   - Hvis du bruger et dedikeret subdomæne (f.eks. `receipts.ditdomaene.dk`) eller vil fange alle plus-adresser:
     - Klik **Add rule** eller rediger **Catch-all**.
     - **Custom address**: Vælg `Custom address` -> Tast `receipts` (eller Catch-all `*`).
     - **Action**: Vælg `Send to a Worker`.
     - **Destination**: Vælg din worker (`peng-email-inbound`).
4. Klik **Save**.

---

## 5. Test at det virker

1. Gå til **Indstillinger** i Peng.
2. Find kortet **Storebox / Nexi Kvitteringer**.
3. Klik på **Kopier e-mail** for at få din husstands adresse.
4. Send/videresend en Storebox-mail til denne adresse.
5. Inden for få sekunder vises mailen i **Historik over indkomne e-mails** med grønt status-badge (`Gennemført`), og kvitteringerne er automatisk koblet til dine transaktioner!
