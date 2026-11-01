class VoucherAPIError(Exception):
    def __init__(self, status, code, message=None, details=None):
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code
        self.details = details or {}

    def response(self):
        response = {"status": "error", "code": self.code, "message": self.message}
        response.update(self.details)
        return response
