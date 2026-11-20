from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.responses import Response

from app.core.errors import error_response


class ApiCORSMiddleware(CORSMiddleware):
    def preflight_response(self, request_headers: Headers) -> Response:
        response = super().preflight_response(request_headers)
        if response.status_code == 200:
            return response
        rejected = error_response("CORS_REJECTED", "Yêu cầu không được phép.", response.status_code)
        for key, value in response.headers.items():
            if key not in {"content-type", "content-length"}:
                rejected.headers[key] = value
        return rejected
