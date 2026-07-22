# Realtime Collaboration Specification

This specification defines the realtime collaboration requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR files at `/tmp/archidekt.har` and `/tmp/archidekt2.har`.

## ADDED Requirements

### Requirement: Provider SHALL implement collaborative WebSocket endpoint

The Archidekt provider SHALL establish WebSocket connections for realtime collaborative deck editing using the `/api/ws/collaborative/{id}/` endpoint. This endpoint enables multiple users to edit the same deck simultaneously with live updates.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/ws/collaborative/23394508/?clientId=_Hdxu9Dul4&token=eyJhbGciOiJIUzI1NiIs...`
- Entry: `GET /api/ws/collaborative/24299438/?clientId=UIJPmN-Hoh&token=eyJhbGciOiJIUzI1NiIs...`
- Status: 101 (Switching Protocols)
- Content-Type: text/plain
- Content-Size: 0 bytes
- WebSocket upgrade with JWT token authentication

#### Scenario: Establish WebSocket connection
- **WHEN** user initiates collaborative editing session
- **AND** deck ID is 23394508
- **AND** user has valid JWT token
- **THEN** provider makes WebSocket connection request to `/api/ws/collaborative/23394508/`
- **AND** request includes `clientId` query parameter with unique client identifier
- **AND** request includes `token` query parameter with valid JWT token
- **AND** server responds with HTTP 101 Switching Protocols
- **AND** WebSocket connection is established

#### Scenario: WebSocket authentication
- **WHEN** establishing WebSocket connection
- **THEN** provider includes JWT token in query string
- **AND** token has type `access` (as shown in decoded JWT: `"token_type": "access"`)
- **AND** token includes `user_id` claim identifying the authenticated user
- **AND** server validates token before accepting connection

#### Scenario: Unique client ID
- **WHEN** establishing WebSocket connection
- **THEN** provider generates unique `clientId` for each connection
- **AND** `clientId` is included in query parameters
- **AND** server uses `clientId` to identify the connection

#### Scenario: Handle WebSocket messages
- **WHEN** WebSocket connection is established
- **THEN** provider can send and receive JSON messages
- **AND** messages include operation type (e.g., "add", "remove", "modify")
- **AND** messages include card information and position data
- **AND** provider broadcasts changes to all connected clients

#### Scenario: WebSocket error handling
- **WHEN** WebSocket connection fails or is rejected
- **THEN** provider receives error response or connection closes
- **AND** provider raises appropriate exception
- **AND** provider logs error with details

#### Scenario: Multiple collaborative sessions
- **WHEN** user has multiple decks open for collaboration
- **THEN** provider can maintain multiple WebSocket connections
- **AND** each connection is to a different `/api/ws/collaborative/{deck_id}/` endpoint
- **AND** each connection has its own `clientId`
