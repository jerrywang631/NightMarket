# Voucher Adventure API

Voucher Adventure uses server-authoritative, versioned sessions. Correct
answers, formulas, final bundle prices, and full correct feedback are not
returned before grading permits them.

The current identity mode is `MVP/DEVELOPMENT_IDENTITY`. `player_id` is a
client-generated correlation identifier, not a secure credential. Session IDs
are unpredictable UUIDs and no endpoint lists another player's sessions.

## Storage and migrations

- With `DATABASE_URL`, Voucher Session state uses PostgreSQL/Supabase.
- Without it, state uses `backend/database/voucher_sessions.db`.
- Existing Vendor, Dialogue, and Challenge storage is unchanged.
- Migration files are under `backend/migrations/` and are applied once using
  `voucher_schema_migrations`.

Apply explicitly from the backend directory:

```powershell
py -3.11 migrate_voucher_sessions.py
```

For PostgreSQL, set `DATABASE_URL` first. Application startup also ensures the
migration is applied.

## Shared conventions

All mutating endpoints require:

```http
Idempotency-Key: <client-generated UUID>
Content-Type: application/json
```

Reusing a key with a different operation or body returns `409
IDEMPOTENCY_KEY_REUSED`. Money is always an integer number of cents.

Errors use:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable description"
}
```

## Shared entry NPC

Hokkien3 and Hokkien4 share the same static entry NPC and Vendor:

- NPC: `npc_va_guide` (`Voucher Guide`)
- Vendor: `v_va_guide`
- Root Dialogue node: `n_va_guide_intro`
- Items: empty

The Guide uses one `n_va_guide_intro` node containing the invitation, Offer
instructions, and `$40` shopping instruction. Enter/Later are exposed directly
on this node, and both option labels contain only English and Traditional
Chinese.

The `o_va_guide_enter` option emits `e_va_guide_start`, whose event type is
`START_MINIGAME`. Its metadata is restricted to exactly
`{"minigame_id":"voucher_adventure"}`; static-content validation rejects a
different minigame or arbitrary scene target. `o_va_guide_later` emits no
event. No additional API endpoint is required.

The node contains the supplied English and Traditional Chinese text, reviewed
POJ, and one WAV generated from that POJ with `facebook/mms-tts-nan`. Regenerate
the clip and repopulate both static databases from the backend directory with:

```powershell
python -X utf8 populate_voucher_adventure.py --generate-guide-audio
```

The five Offer Vendor dialogue options contain only English and Traditional
Chinese (`English / 漢字`). POJ remains available on the spoken dialogue lines,
but is intentionally omitted from option text.

## Create a session

```http
POST /api/v1/voucher-adventure/sessions
```

```json
{
  "player_id": "local-player-id",
  "difficulty": "easy",
  "content_version": "v1"
}
```

The response contains five Vendor/Offer instance mappings but no questions or
answers. Only one `ACTIVE` session per player and content version is allowed.

```json
{
  "status": "success",
  "data": {
    "session_id": "va_session_<uuid>",
    "seed": 18273,
    "content_version": "v1",
    "difficulty": "easy",
    "identity_mode": "MVP/DEVELOPMENT_IDENTITY",
    "time_limit_seconds": null,
    "shopping_bonus": {
      "vendor_target": 0,
      "required_for_completion": false
    },
    "vendors": [
      {
        "vendor_id": "v_va_001",
        "offer_instance_id": "voi_<uuid>",
        "dialogue_node_id": "n_va_v1_greet"
      }
    ]
  }
}
```

Unknown versions return `400 UNSUPPORTED_CONTENT_VERSION`. A second active
session returns `409 ACTIVE_SESSION_EXISTS` with the current `session_id`.

`v1` is the only public supported version. It has completed language, POJ,
audio, and release review; no server feature flag is required. Unknown and
retired versions return `UNSUPPORTED_CONTENT_VERSION`.

## Session-aware dialogue

```http
GET /api/v1/dialogue/{node_id}?session_id={session_id}
```

The existing route remains unchanged without `session_id`. With a session it
renders the materialized price Variant, translations, node audio, and dynamic
Reveal metadata:

```json
{
  "event_type": "VOUCHER_OFFER_REVEALED",
  "metadata": "{\"session_id\":\"...\",\"offer_instance_id\":\"...\",\"vendor_id\":\"v_va_001\",\"offer_id\":\"pepper_bun\"}"
}
```

## Reveal an offer

```http
POST /api/v1/voucher-adventure/sessions/{session_id}/offers/{offer_instance_id}/reveal
```

```json
{
  "dialogue_node_id": "n_va_v1_offer",
  "option_id": "o_va_v1_confirm_offer",
  "remaining_ms": 68000
}
```

`remaining_ms` is optional and applies only to Hard sessions. The response
contains safe Offer inputs and question instances. It deliberately omits
`bundle_price_cents`, effective unit price, answers, hints, formulas, and full
correct feedback.

## Submit an answer

```http
POST /api/v1/voucher-adventure/attempts
```

```json
{
  "session_id": "va_session_<uuid>",
  "question_instance_id": "vqi_<uuid>",
  "answer": 400,
  "answer_unit": "MONEY_CENTS",
  "attempt_number": 1,
  "english_support_used": false,
  "response_time_ms": 8200,
  "remaining_ms": 68000
}
```

`attempt_number` must equal the server's expected number. A conflict returns
`409 UNEXPECTED_ATTEMPT_NUMBER` and `expected_attempt_number`.

Wrong answers return one of `RETRY_ONLY`, `RULE_HINT`, or `FORMULA_HINT`.
Correct answers return `CORRECT`. Only after the last required question for an
Offer is correct does the response include:

```json
{
  "offer_resolved": {
    "bundle_price_cents": 1200,
    "effective_unit_price_cents": 600
  }
}
```

## Save the Basket

```http
PUT /api/v1/voucher-adventure/sessions/{session_id}/basket
```

```json
{
  "client_revision": 1,
  "remaining_ms": 68000,
  "items": [
    {
      "offer_instance_id": "voi_<uuid>",
      "quantity": 2
    }
  ]
}
```

The request is a complete snapshot. Each submitted `offer_instance_id` may
appear once and its `quantity` must equal that Offer's `bundle_size`. Omit an
Offer to leave it unpurchased. The server recalculates every price, requires
resolved Offers, and rejects totals above 4000 cents. Revisions must increase
by exactly one.

## Record behavior and timer events

```http
POST /api/v1/voucher-adventure/sessions/{session_id}/events
```

Supported types:

- `ENGLISH_SUPPORT_USED`
- `AUDIO_REPLAYED`
- `SESSION_STARTED`
- `SESSION_PAUSED`
- `SESSION_RESUMED`
- `TIMER_CHECKPOINT`

```json
{
  "event_id": "client-event-uuid",
  "event_type": "TIMER_CHECKPOINT",
  "offer_instance_id": null,
  "dialogue_node_id": null,
  "occurred_at": "2026-10-28T18:00:00Z",
  "metadata": {
    "remaining_ms": 68400
  }
}
```

Timer values are monotonic and stale client events cannot restore time. Timer
precision is intentionally checkpoint-based because it controls only a bonus.

## Restore a session

```http
GET /api/v1/voucher-adventure/sessions/{session_id}
```

The response includes status, content version, timer checkpoint, Vendor
Reveal/completion state, safe question progress, submitted attempts, Basket,
English-support usage, and audio replay count. Unrevealed Vendors contain only
their IDs and root Dialogue mapping. Completed Offers may include final prices.

Attempts for an incomplete question expose only safe progress metadata; their
submitted `answer` and `feedback_en` are omitted. Once that question is
completed, its attempt history includes those fields for review.

Sessions expire after seven days. Completed sessions remain readable.

## Complete or abandon

```http
POST /api/v1/voucher-adventure/sessions/{session_id}/complete
```

```json
{
  "basket_revision": 4
}
```

The server recomputes learning and shopping results from saved state. Missing
learning work returns `409 LEARNING_INCOMPLETE`. A stale Basket returns `409
STALE_BASKET_REVISION`. The Offer Explorer target and Hard speed result are
bonuses and never block learning completion. There is no exact-spend bonus;
4000 cents is only the Basket budget ceiling.

```http
POST /api/v1/voucher-adventure/sessions/{session_id}/abandon
```

An abandoned session releases the one-active-session constraint. Completed
sessions cannot be abandoned.

## Released content

`v1` contains 45 released question templates:

- Five Offers
- Three price Variants per Offer
- `RULE_MEANING`, `PRICE_CALCULATION`, and `TRANSFER`

Variants A, B, and C are `APPROVED` and selectable. The Session seed selects a
stable Variant for each Offer. The selected Variant, prices, questions, and
transfer source are stored with the Session, so Restore never rerolls content.

The internal review artifact is
`voucher_adventure_v1_review.json`. It contains all 15 Offer/Variant entries
and all 45 question definitions, including correct answers, and therefore must
never be returned by a player endpoint.

Regenerate the manifest from the backend directory:

```powershell
py -3.11 generate_voucher_v1_review.py
```

Regenerate the ten B/C greeting audio drafts as well:

```powershell
py -3.11 generate_voucher_v1_review.py --generate-audio
```

B/C audio was generated with `facebook/mms-tts-nan` using the POJ line as
input and has now been approved. Offer-node audio and all Variant A audio are
the released baseline recordings.
