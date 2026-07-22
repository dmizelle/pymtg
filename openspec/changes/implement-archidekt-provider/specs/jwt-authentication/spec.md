# JWT Authentication Specification

This specification defines the JWT Bearer token authentication requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL use JWT authentication

The Archidekt provider SHALL authenticate using JWT Bearer tokens obtained via POST request to `/api/rest-auth/login/` endpoint. The provider MUST NOT use session cookies or CSRF tokens for authentication.

**Evidence from HAR file (Entry #2)**:
- URL: `https://archidekt.com/api/rest-auth/login/`
- Method: POST
- Content-Type: application/json
- Request body: `{"username": "phobos_pymtg", "password": "cyb0rgab!"}`
- Response: Contains `access_token`, `refresh_token`, `token`, and `user` object
- Authorization header used in subsequent requests: `JWT <access_token>`

#### Scenario: Successful JWT authentication
- **WHEN** user provides valid username and password
- **THEN** provider POSTs credentials to `/api/rest-auth/login/`
- **AND** provider receives response containing `access_token`, `refresh_token`, and `token`
- **AND** provider stores `access_token` for use in Authorization header
- **AND** provider sets Authorization header to `JWT <access_token>` for all authenticated requests

#### Scenario: Failed authentication with invalid credentials
- **WHEN** user provides invalid username and/or password
- **THEN** provider POSTs credentials to `/api/rest-auth/login/`
- **AND** provider receives HTTP 401 or 403 response
- **AND** provider raises `ArchidektAuthenticationError` with message indicating invalid credentials

#### Scenario: Authentication with network error
- **WHEN** network error occurs during login request
- **THEN** provider raises `NetworkError` with original exception

#### Scenario: Token stored securely in memory
- **WHEN** authentication succeeds
- **THEN** provider stores access token in memory
- **AND** provider stores refresh token in memory
- **AND** provider clears plaintext password from memory immediately after authentication

#### Scenario: Credentials not persisted to disk
- **WHEN** authentication succeeds
- **THEN** provider MUST NOT write credentials to disk
- **AND** provider MUST NOT write tokens to disk
- **AND** tokens are stored only in memory for the duration of the provider instance

---

### Requirement: Provider SHALL support token-based authentication header

The provider SHALL include the JWT access token in the Authorization header of all authenticated requests using the format `JWT <token>`.

**Evidence from HAR file**:
- Entry #4, #11, #14, #19: GET `/api/users/1071357/notificationCount/` with `authorization: JWT eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- Entry #16: POST `/api/decks/v2/` with `authorization: JWT <token>`
- Entry #24, #25, #28, #30: PATCH `/api/decks/{id}/modifyCards/v2/` with `authorization: JWT <token>`

#### Scenario: Authenticated request includes JWT header
- **WHEN** provider makes authenticated request to any Archidekt API endpoint
- **THEN** request includes header `Authorization: JWT <access_token>`

#### Scenario: Unauthenticated request omits Authorization header
- **WHEN** provider makes request to public endpoint (e.g., card search without authentication)
- **THEN** request does not include Authorization header
- **AND** request succeeds if endpoint allows unauthenticated access

---

### Requirement: Provider SHALL support optional authentication for card search

The card search endpoint (`/api/cards/v2/`) SHALL work without authentication. However, authenticated searches MAY return different results or have higher rate limits.

**Evidence from HAR file**:
- Entry #15: GET `/api/cards/v2/?nameSearch=Myra...` without Authorization header, status 200
- Entry #23: GET `/api/cards/v2/?nameSearch=sol%20ring...` without Authorization header, status 200
- Entry #26: GET `/api/cards/v2/?name=Arcane%20Signet...` with Authorization header, status 200

#### Scenario: Card search without authentication
- **WHEN** user searches for cards without providing credentials
- **THEN** provider makes request without Authorization header
- **AND** request succeeds and returns card results

#### Scenario: Card search with authentication
- **WHEN** user is authenticated and searches for cards
- **THEN** provider includes Authorization header in request
- **AND** request succeeds and returns card results

---

### Requirement: Provider SHALL require authentication for deck operations

All deck-related operations SHALL require authentication. The provider SHALL raise an error if authentication is not established before attempting deck operations.

**Evidence from HAR file**:
- All deck operations (Entries #16, #24, #25, #28, #30) include Authorization header
- Deck creation, modification, and retrieval all use authenticated requests

#### Scenario: Create deck without authentication
- **WHEN** user attempts to create deck without being authenticated
- **THEN** provider raises `ArchidektAuthenticationError` before making request

#### Scenario: Get deck without authentication
- **WHEN** user attempts to retrieve deck without being authenticated
- **THEN** provider raises `ArchidektAuthenticationError` before making request

#### Scenario: Modify deck cards without authentication
- **WHEN** user attempts to add/remove cards from deck without being authenticated
- **THEN** provider raises `ArchidektAuthenticationError` before making request

---

### Requirement: Provider SHALL support authentication state checking

The provider SHALL provide a method to check if it is currently authenticated.

#### Scenario: Check authentication status when authenticated
- **WHEN** user has successfully authenticated
- **AND** provider.is_authenticated() is called
- **THEN** returns `True`

#### Scenario: Check authentication status when not authenticated
- **WHEN** user has not authenticated
- **AND** provider.is_authenticated() is called
- **THEN** returns `False`

#### Scenario: Check authentication status after failed authentication
- **WHEN** authentication attempt fails
- **AND** provider.is_authenticated() is called
- **THEN** returns `False`

---

### Requirement: Provider SHALL clear authentication state on logout

The provider SHALL provide a method to clear authentication state, removing tokens from memory.

#### Scenario: Clear authentication
- **WHEN** user calls logout or clear_auth method
- **THEN** access token is cleared from memory
- **AND** refresh token is cleared from memory
- **AND** subsequent is_authenticated() returns `False`
- **AND** subsequent authenticated requests raise `ArchidektAuthenticationError`

---

### Requirement: Provider SHALL handle token in response headers

The provider SHALL extract and use the JWT token from the login response, which is returned in the response body as `access_token`. The token SHALL be used in the Authorization header for subsequent requests.

**Evidence from HAR file (Entry #2 response)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgzODg0NDAzLCJpYXQiOjE3ODM4ODA4MDMsImp0aSI6IjQ3YjdjZDc1OWE0MjRlOTJhMGFiOTBkMmY1MDU5MDFjIiwidXNlcl9pZCI6IjEwNzEzNTcifQ.1IC8X5A1toMT6pFO1D46TdsyJqxarpK1FRCfsfZ9u5Y",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc4NzMzNjgwMywiaWF0IjoxNzgzODgwODAzLCJqdGkiOiI4NDc4YzA3OTA5MDM0YjRmODdhOTRlMjg5YTYwM2FkOCIsInVzZXJfaWQiOiIxMDcxMzU3In0.rr2qoT_JBEn2-FnjTP16hOcZy1HkTDuKzzFg_zbAEGA",
  "user": { ... },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgzODg0NDAzLCJpYXQiOjE3ODM4ODA4MDMsImp0aSI6IjQ3YjdjZDc1OWE0MjRlOTJhMGFiOTBkMmY1MDU5MDFjIiwidXNlcl9pZCI6IjEwNzEzNTcifQ.1IC8X5A1toMT6pFO1D46TdsyJqxarpK1FRCfsfZ9u5Y"
}
```

#### Scenario: Token extraction from login response
- **WHEN** provider receives successful login response
- **THEN** provider extracts `access_token` from response JSON
- **AND** provider stores `access_token` for use in Authorization header

#### Scenario: Use token for subsequent requests
- **WHEN** provider makes authenticated request after successful login
- **THEN** provider uses stored `access_token` in Authorization header
- **AND** header format is exactly `JWT <access_token>` (with space)
