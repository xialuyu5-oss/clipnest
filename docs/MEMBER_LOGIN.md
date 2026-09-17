# Bilibili member login

The current account integration supports **Bilibili only**, in local loopback mode. It can request formats available to the connected account; it does not create membership rights or guarantee HD/4K availability.

## Use

1. Start the local service and open its loopback URL.
2. Open **Account** and generate a Bilibili QR code.
3. Scan and approve it in the official Bilibili app. The website checks the returned login state.
4. Enable use of the connected account for Bilibili analysis, then analyze the video again.
5. Choose one of the actual returned formats and confirm the download.

The UI can save the QR image and check again when returning to the page. Same-phone album recognition depends on the official app version and has not been validated end-to-end. QR generation, cancellation, expiry handling, and simulated login transitions have been tested; real member authorization and a resulting member-HD file still require acceptance testing.

## Credential lifecycle

Platform cookies are held in process memory and passed only to the relevant download worker. They are not written to `.env`, task metadata, browser storage, downloaded-file metadata or source archives. They are sent only to permitted HTTPS Bilibili domains, not to a third-party QR service. The application does not collect an account password or persist an account profile/refresh token.

The in-memory session has a maximum lifetime of 24 hours and may expire earlier at the platform. Restarting the service requires a new login. Disconnecting clears the local session, invalidates related analysis and cancels associated unfinished downloads; it does not sign out the official mobile app. Process memory is not a guarantee against OS swap or crash dumps.

Changing/disconnecting accounts requires fresh analysis. A resumed member task after a server restart needs its account connected again.

## Deployment boundary

Member mode checks both Host and the actual loopback peer. Disable it for LAN, Docker or public hosting. A configured public origin also prevents member login. This is a platform QR web flow, not a promised stable third-party OAuth contract. Upstream behavior can change.
