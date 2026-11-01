DELETE FROM voucher_attempts
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'va_1'
);

DELETE FROM voucher_basket_items
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'va_1'
);

DELETE FROM voucher_session_questions
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'va_1'
);

DELETE FROM voucher_session_events
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'va_1'
);

DELETE FROM voucher_session_offers
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'va_1'
);

DELETE FROM voucher_sessions WHERE content_version = 'va_1';
UPDATE voucher_sessions SET content_version = 'v1' WHERE content_version = 'va_2';
UPDATE voucher_session_offers
SET content_status = 'APPROVED', approved = 1
WHERE session_id IN (
    SELECT session_id FROM voucher_sessions WHERE content_version = 'v1'
);

-- Cached create/restore responses may contain retired version names.
DELETE FROM voucher_idempotency;
