## ADDED Requirements

### API Verification Context
Based on subagent investigation (July 2026):
- **Scryfall**: No auth required for most endpoints. OAuth in private beta (not needed for v1)
- **Archidekt**: No auth for public endpoints. Session cookies for authenticated deck access (user will provide HAR files)
- **Moxfield**: Requires Parse.bot API key passed via `X-API-Key` header
- **TCGPlayer**: Requires OAuth2 flow, new access currently closed
- **Cardmarket**: Requires OAuth 1.0a (Access Token + Access Token Secret)
- **Deckbox**: No public API available

### Requirement: Each provider SHALL handle its own authentication
Each provider MUST handle its own authentication mechanism independently. The base Provider class SHALL NOT enforce a specific authentication mechanism.

#### Scenario: No authentication provider
- **WHEN** user instantiates Scryfall()
- **THEN** system requires no authentication parameters

#### Scenario: Session authentication provider
- **WHEN** user instantiates Archidekt(username="user", password="pass")
- **THEN** system handles login and session cookie management internally

#### Scenario: API key authentication provider
- **WHEN** user instantiates Deckbox(api_key="key123")
- **THEN** system stores the API key and includes it in requests

#### Scenario: OAuth2 authentication provider
- **WHEN** user instantiates TCGPlayer(client_id="id", client_secret="secret")
- **THEN** system handles OAuth2 token acquisition and refresh internally

---

### Requirement: Session-based providers SHALL handle login flow
Providers that use session cookies (Archidekt, Moxfield) MUST implement the full login flow: credentials submission, cookie storage, CSRF token handling.

#### Scenario: Archidekt login
- **WHEN** user instantiates Archidekt with username and password
- **THEN** system POSTs credentials to /accounts/login/, stores sessionid and csrftoken cookies
- **BASE URL**: `https://archidekt.com`
- **Login Endpoint**: `/accounts/login/`
- **Required Headers**: `Content-Type: application/x-www-form-urlencoded`
- **Required Fields**: `username`, `password`
- **Cookie Names**: `sessionid`, `csrftoken`

#### Scenario: Moxfield via Parse.bot
- **WHEN** user instantiates Moxfield with Parse.bot API key
- **THEN** system includes `X-API-Key: <key>` header in all requests
- **BASE URL**: `https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/`
- **Note**: Moxfield itself has no official API; Parse.bot provides a wrapper

#### Scenario: CSRF token handling
- **WHEN** a provider requires CSRF protection
- **THEN** system includes X-CSRFToken header with the csrftoken cookie value
- **Archidekt**: Requires `X-CSRFToken` header matching csrftoken cookie for authenticated endpoints

---

### Requirement: OAuth2 providers SHALL implement token management
Providers that use OAuth2 (TCGPlayer, Cardmarket) MUST implement OAuth2 token acquisition, storage, refresh, and revocation.

#### Scenario: TCGPlayer token acquisition
- **WHEN** user instantiates TCGPlayer with client credentials
- **THEN** system acquires access token from TCGPlayer OAuth flow
- **BASE URL**: `https://api.tcgplayer.com`
- **Token Endpoint**: Implicit in OAuth flow (not /oauth/token/)
- **Header**: `X-Tcg-Access-Token: <token>`
- **Status**: New access currently closed to new developers
- **Note**: Requires pre-approved application at https://docs.tcgplayer.com

#### Scenario: Cardmarket OAuth 1.0a flow
- **WHEN** user instantiates Cardmarket with OAuth credentials
- **THEN** system implements OAuth 1.0a flow with Access Token + Access Token Secret
- **BASE URL**: `https://apiv2.cardmarket.com`
- **API Version**: 2.0 (release1)
- **Format**: Supports JSON (add `/output.json/` to endpoint path)
- **Header**: `Authorization: OAuth oauth_token=<token>,oauth_token_secret=<secret>`
- **Status**: New access currently closed to new developers
- **Note**: Requires pre-approved application at https://api.cardmarket.com

#### Scenario: Token refresh
- **WHEN** access token expires
- **THEN** system automatically acquires a new token using refresh token or client credentials
- **TCGPlayer**: Uses client credentials flow for refresh
- **Cardmarket**: Uses OAuth 1.0a token renewal

#### Scenario: Token storage
- **WHEN** token is acquired
- **THEN** system stores token securely in the provider instance (not on disk)
- **Both providers**: Store tokens in memory only, never persist to disk

---

### Requirement: Authentication errors SHALL be clearly reported
When authentication fails, providers MUST raise AuthenticationError with clear information about what went wrong.

#### Scenario: Invalid credentials
- **WHEN** user provides invalid username/password
- **THEN** system raises AuthenticationError with message indicating invalid credentials

#### Scenario: Expired session
- **WHEN** session has expired
- **THEN** system raises AuthenticationError with message indicating session expired

#### Scenario: OAuth2 token invalid
- **WHEN** OAuth2 token is invalid or expired
- **THEN** system raises AuthenticationError with message indicating token issue

---

### Requirement: Providers SHALL support authentication testing
Each provider MUST provide a method to test if authentication is valid.

#### Scenario: Test Scryfall (no auth)
- **WHEN** user calls scryfall.is_authenticated()
- **THEN** system returns True (Scryfall requires no auth)

#### Scenario: Test Archidekt session
- **WHEN** user calls archidekt.is_authenticated()
- **THEN** system makes a test request and returns True if session is valid

#### Scenario: Test OAuth2 token
- **WHEN** user calls tcgplayer.is_authenticated()
- **THEN** system verifies token is valid and not expired

---

### Requirement: Providers SHALL allow authentication refresh
For providers where authentication can expire, the provider MUST allow refreshing the authentication.

#### Scenario: Refresh session
- **WHEN** user calls archidekt.refresh_auth()
- **THEN** system re-authenticates with stored credentials

#### Scenario: Refresh OAuth2 token
- **WHEN** user calls tcgplayer.refresh_auth()
- **THEN** system acquires a new access token

---

### Requirement: Providers SHALL handle rate limit authentication
Some providers may require authentication for rate limit purposes (API keys for higher limits). Providers MUST support this.

#### Scenario: API key for higher limits
- **WHEN** user provides API key for a provider that supports it
- **THEN** system includes the API key in requests for higher rate limits

#### Scenario: Optional API key
- **WHEN** a provider has optional API key for higher limits
- **THEN** system works without API key but with lower rate limits

---

### Requirement: Authentication SHALL NOT be persisted to disk
Providers MUST NOT persist authentication credentials or tokens to disk by default. All authentication state SHALL be in-memory only.

#### Scenario: In-memory only
- **WHEN** user authenticates with a provider
- **THEN** system stores auth state only in the provider instance's memory

#### Scenario: No credential leakage
- **WHEN** provider instance is garbage collected
- **THEN** authentication credentials are cleared from memory

---

### Requirement: Providers SHALL support environment variable authentication
While not the primary method, providers MUST support reading authentication from environment variables as a convenience.

#### Scenario: From environment
- **WHEN** user calls Archidekt.from_env()
- **THEN** system reads username and password from ARCHIDEKT_USERNAME and ARCHIDEKT_PASSWORD environment variables

#### Scenario: Mixed sources
- **WHEN** user provides some auth via constructor and some via environment
- **THEN** system uses constructor values and falls back to environment for missing values

---

### Requirement: Providers SHALL persist sessions across requests within instance
For session-based authentication providers (Archidekt, Moxfield), the provider MUST maintain session cookies across multiple requests within the same provider instance.

#### Scenario: Multiple requests with session
- **WHEN** user creates Archidekt instance and makes multiple requests
- **THEN** session cookies are maintained across all requests without re-authentication

#### Scenario: Separate instances have separate sessions
- **WHEN** user creates two Archidekt instances with different credentials
- **THEN** each instance maintains its own separate session

#### Scenario: Session persistence uses requests.Session
- **WHEN** provider makes HTTP requests
- **THEN** it uses requests.Session for automatic cookie persistence

#### Scenario: Session not persisted to disk
- **WHEN** authentication occurs
- **THEN** session cookies are stored in memory only, not on disk

---

### Requirement: Providers SHALL document authentication requirements
Each provider MUST have clear documentation about its authentication requirements: what's needed, how to obtain it, any approval processes.

#### Scenario: Provider auth documentation
- **WHEN** user views help(Archidekt)
- **THEN** system displays authentication requirements (username/password)

#### Scenario: OAuth2 approval process
- **WHEN** user views help(TCGPlayer)
- **THEN** system displays information about required approval process
