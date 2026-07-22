# Social Features Specification

This specification defines the social features requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR files at `/tmp/archidekt.har` and `/tmp/archidekt2.har`.

## ADDED Requirements

### Requirement: Provider SHALL implement comments endpoint

The Archidekt provider SHALL retrieve comments for a deck using the `/api/comments/{comment_id}/` endpoint with GET requests. This endpoint returns comment thread information including the comment, owner, and child comments.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/comments/23446857/?page=1&orderBy=-points`
- Entry: `GET /api/comments/24354478/?page=1&orderBy=-points`
- Status: 200
- Response: JSON object with comment details
- Content-Type: application/json
- Content-Size: 323-328 bytes

#### Scenario: Retrieve comment by ID
- **WHEN** user requests a specific comment
- **AND** comment ID is 23446857
- **THEN** provider makes GET request to `/api/comments/23446857/`
- **AND** provider includes JWT Authorization header
- **AND** response contains comment object

#### Scenario: Comment with pagination
- **WHEN** user requests comments with pagination
- **AND** page is 1
- **AND** order is by points descending
- **THEN** provider makes GET request with `?page=1&orderBy=-points`
- **AND** response contains paginated comment results

#### Scenario: Comment object structure
- **WHEN** provider receives comment response
- **THEN** the comment object contains:
  - `id`: integer - comment ID
  - `title`: string or null - comment title
  - `text`: string or null - comment text
  - `owner`: object - user who owns the comment
  - `deck`: object - reference to the deck being commented on
  - `parent`: object or null - parent comment for threads
  - `originalPost`: object or null - original post reference
  - `childrenCount`: integer - number of child comments
  - `children`: object - paginated child comments
  - `createdAt`: string - creation timestamp
  - `editedAt`: string or null - last edit timestamp
  - `points`: integer - upvote count
  - `userInput`: integer - user input indicator
  - `archived`: boolean - whether comment is archived
  - `locked`: boolean - whether comment is locked
  - `featured`: string or null - featured status
  - `type`: integer - comment type

#### Scenario: Comment children structure
- **WHEN** comment has child comments
- **THEN** children object contains:
  - `links`: object with `next` and `previous` pagination URLs
  - `count`: integer - total number of children
  - `results`: array - list of child comment objects

---

### Requirement: Provider SHALL implement notification count endpoint

The Archidekt provider SHALL retrieve the unread notification count for a user using the `/api/users/{user_id}/notificationCount/` endpoint with GET requests. This endpoint returns the number of unread notifications and Patreon account status.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/users/1071357/notificationCount/` (multiple calls)
- Status: 200
- Response: `{"notificationCount": 0, "patreonAccount": null}`
- Content-Type: application/json
- Content-Size: 61 bytes

#### Scenario: Retrieve notification count
- **WHEN** user requests their notification count
- **AND** user ID is 1071357
- **THEN** provider makes GET request to `/api/users/1071357/notificationCount/`
- **AND** provider includes JWT Authorization header
- **AND** response contains notification count object

#### Scenario: Notification count object structure
- **WHEN** provider receives notification count response
- **THEN** the response object contains:
  - `notificationCount`: integer - number of unread notifications
  - `patreonAccount`: object or null - Patreon account information if applicable

#### Scenario: User with notifications
- **WHEN** user has unread notifications
- **THEN** `notificationCount` is greater than 0
- **AND** provider can use this to indicate new activity

#### Scenario: User with no notifications
- **WHEN** user has no unread notifications
- **THEN** `notificationCount` is 0
- **AND** `patreonAccount` may be null or contain account details
