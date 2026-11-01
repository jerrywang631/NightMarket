"""Flask routes and MVP rate limits for Voucher Adventure."""

from collections import defaultdict, deque
from functools import wraps
from threading import Lock
import time

from flask import jsonify, request

from .errors import VoucherAPIError


class VoucherRateLimiter:
    """Best-effort per-process limiter for the unauthenticated MVP."""

    def __init__(self):
        self.requests = defaultdict(deque)
        self.lock = Lock()

    def check(self, bucket, identity, limit, window_seconds=60):
        now = time.monotonic()
        key = (bucket, identity)
        with self.lock:
            history = self.requests[key]
            cutoff = now - window_seconds
            while history and history[0] <= cutoff:
                history.popleft()
            if len(history) >= limit:
                retry_after = max(1, int(window_seconds - (now - history[0])))
                raise VoucherAPIError(
                    429,
                    "RATE_LIMITED",
                    "Too many Voucher Adventure requests",
                    {"retry_after_seconds": retry_after},
                )
            history.append(now)


def register_voucher_routes(app, service):
    limiter = VoucherRateLimiter()

    def endpoint(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            try:
                data, status = handler(*args, **kwargs)
                return jsonify({"status": "success", "data": data}), status
            except VoucherAPIError as error:
                return jsonify(error.response()), error.status

        return wrapped

    def json_body():
        body = request.get_json(silent=True)
        if body is None:
            return {}
        if not isinstance(body, dict):
            raise VoucherAPIError(
                400, "INVALID_JSON_BODY", "JSON body must be an object"
            )
        return body

    def request_identity(body=None, session_id=None):
        body = body or {}
        return ":".join(
            part
            for part in (
                request.remote_addr or "unknown",
                str(body.get("player_id") or ""),
                str(session_id or body.get("session_id") or ""),
            )
            if part
        )

    @app.route("/api/v1/voucher-adventure/sessions", methods=["POST"])
    @endpoint
    def create_voucher_session():
        body = json_body()
        limiter.check("create", request_identity(body), 10)
        return service.create_session(body, request.headers.get("Idempotency-Key"))

    @app.route("/api/v1/voucher-adventure/sessions/<session_id>", methods=["GET"])
    @endpoint
    def get_voucher_session(session_id):
        return service.get_session(session_id)

    @app.route(
        "/api/v1/voucher-adventure/sessions/<session_id>/offers/"
        "<offer_instance_id>/reveal",
        methods=["POST"],
    )
    @endpoint
    def reveal_voucher_offer(session_id, offer_instance_id):
        body = json_body()
        limiter.check("state", request_identity(body, session_id), 120)
        return service.reveal_offer(
            session_id,
            offer_instance_id,
            body,
            request.headers.get("Idempotency-Key"),
        )

    @app.route(
        "/api/v1/voucher-adventure/sessions/<session_id>/basket", methods=["PUT"]
    )
    @endpoint
    def update_voucher_basket(session_id):
        body = json_body()
        limiter.check("state", request_identity(body, session_id), 120)
        return service.update_basket(
            session_id, body, request.headers.get("Idempotency-Key")
        )

    @app.route("/api/v1/voucher-adventure/attempts", methods=["POST"])
    @endpoint
    def submit_voucher_attempt():
        body = json_body()
        limiter.check("attempt", request_identity(body), 120)
        return service.submit_attempt(body, request.headers.get("Idempotency-Key"))

    @app.route(
        "/api/v1/voucher-adventure/sessions/<session_id>/events", methods=["POST"]
    )
    @endpoint
    def record_voucher_event(session_id):
        body = json_body()
        limiter.check("event", request_identity(body, session_id), 180)
        return service.record_event(
            session_id, body, request.headers.get("Idempotency-Key")
        )

    @app.route(
        "/api/v1/voucher-adventure/sessions/<session_id>/complete", methods=["POST"]
    )
    @endpoint
    def complete_voucher_session(session_id):
        body = json_body()
        limiter.check("state", request_identity(body, session_id), 120)
        return service.complete_session(
            session_id, body, request.headers.get("Idempotency-Key")
        )

    @app.route(
        "/api/v1/voucher-adventure/sessions/<session_id>/abandon", methods=["POST"]
    )
    @endpoint
    def abandon_voucher_session(session_id):
        body = json_body()
        limiter.check("state", request_identity(body, session_id), 120)
        return service.abandon_session(
            session_id, body, request.headers.get("Idempotency-Key")
        )
