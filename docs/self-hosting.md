# Self-Hosting Peng

Peng er designet med "Self-Hosting First" i tankerne. Den letteste måde at køre systemet på er via Docker, hvor hele applikationen (Frontend + Backend) er pakket ind i én enkelt container, som bruger en lokal SQLite database til at gemme dine transaktioner.

## Krav
- Docker & Docker Compose
- EnableBanking udvikler-konto (gratis) for PSD2 OpenBanking adgang.

## Hurtig Start

1. Klon repositoriet:
   ```bash
   git clone https://github.com/din-github/peng.git
   cd peng
   ```

2. Tilpas `.env` filen (kopiér `.env.example` eller sæt miljøvariablerne direkte):
   ```ini
   PORT=8080
   AUTH_PROVIDER=basic
   PENG_AUTH_USERNAME=admin
   PENG_AUTH_PASSWORD=dit_super_sikre_kodeord
   ```

3. Placer din EnableBanking private key i `./data` mappen (så den bliver mountet rigtigt):
   ```bash
   mkdir -p data
   cp /sti/til/din/enablebanking.pem ./data/enablebanking.pem
   ```

4. Start containeren:
   ```bash
   docker-compose up -d
   ```

5. Gå ind på `http://localhost:8080` i din browser og log ind med dine valgte `basic` auth credentials.

---

## Authentication Muligheder

Du kan styre, hvem der kan tilgå systemet via `AUTH_PROVIDER` miljøvariablen.

### 1. `none` (Standard for lokalt netværk/VPN)
Hvis du kører Peng bag en Tailscale VPN eller lokalt på din egen maskine (hvor port 8080 ikke er eksponeret mod internettet), kan du bruge `AUTH_PROVIDER=none`. Dette slår alt login fra.

### 2. `basic` (Simpelt kodeord)
Beskytter systemet med simpel HTTP Basic Auth.
Kræver, at du definerer `PENG_AUTH_USERNAME` og `PENG_AUTH_PASSWORD`.

### 3. `logto` (OIDC SSO til avancerede setups)
Hvis du allerede har en Self-Hosted SSO udbyder som [Logto](https://logto.io/), kan du lade den styre brugeradgangen:

1. Sæt `AUTH_PROVIDER=logto`.
2. I din `.env` skal du opsætte to variabler for backenden:
   - `OIDC_ISSUER=https://auth.seame.click/oidc`
   - `OIDC_AUDIENCE=https://peng.seame.click/api`
3. Hvis frontendens image skal kende Logto-endpointet (som pt bygges statisk), vil du typisk skulle sætte disse miljøvariabler **inden** bygge-processen (eller kopiere `.env.example`):
   - `VITE_LOGTO_ENDPOINT=https://auth.seame.click/`
   - `VITE_LOGTO_APP_ID=dit_app_id`
   - `VITE_LOGTO_RESOURCE=https://peng.seame.click/api`

---

## Backup & Gendannelse

Al din data (Transaktioner, Regler, Faste Udgifter) ligger sikkert placeret i en standard SQLite-fil.
Med standard `docker-compose.yml` filen placeres den i mappen `./data`.

For at tage en fuld backup, skal du blot kopiere mappen:
```bash
tar -czvf peng_backup_$(date +%F).tar.gz ./data
```
Det anbefales at stoppe containeren med `docker-compose stop` mens backup tages for at forhindre database corruption.
