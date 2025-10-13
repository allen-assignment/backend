# auth_decorators.py
import os, json, jwt
from functools import wraps
from django.http import JsonResponse
from django.conf import settings

JWT_SECRET = getattr(settings, "JWT_SECRET", os.environ.get("JWT_SECRET", "compassignment"))

def _extract_token(request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    try:
        if request.body:
            data = json.loads(request.body)
            if isinstance(data, dict) and data.get("token"):
                request._cached_json = data
                return data["token"]
    except Exception:
        pass
    return request.GET.get("token")

def require_token(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        token = _extract_token(request)
        if not token:
            return JsonResponse({"error": "token required"}, status=401)
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return JsonResponse({"error": "token expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"error": "invalid token"}, status=401)


        request.claims = claims
        request.user_id = claims.get("user_id")
        request.user_type = claims.get("user_type")               # 0=merchant, 1=customer
        request.merchant_id_from_token = claims.get("merchant_id")
        return view(request, *args, **kwargs)
    return _wrapped

def optional_token(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):

        token = None
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1].strip()
        if not token and request.body:
            try:
                data = json.loads(request.body or b"{}")
                if isinstance(data, dict):
                    token = data.get("token")
            except Exception:
                pass
        if not token:
            token = request.GET.get("token")

        if token:
            try:
                claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                request.claims = claims
                request.user_id = claims.get("user_id")
                request.user_type = claims.get("user_type")
                request.merchant_id_from_token = claims.get("merchant_id")
            except jwt.ExpiredSignatureError:
                return JsonResponse({"error": "token expired"}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({"error": "invalid token"}, status=401)

        return view(request, *args, **kwargs)
    return _wrapped


def inject_identity_into_body(view):
    """
        POST/PUT/PATCH
    """
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if request.method not in ("POST", "PUT", "PATCH"):
            return view(request, *args, **kwargs)
        claims = getattr(request, "claims", None)
        if not claims:
            return JsonResponse({"error": "token required"}, status=401)
        try:
            data = getattr(request, "_cached_json", None)
            if data is None:
                data = json.loads(request.body or b"{}")
            data["user_id"] = claims.get("user_id")
            if str(claims.get("user_type", "1")) == "0":
                mid = claims.get("merchant_id")
                if not mid:
                    return JsonResponse({"error": "merchant_id missing in token"}, status=403)
                data["merchant_id"] = mid
            request._body = json.dumps(data).encode("utf-8")
        except Exception as e:
            return JsonResponse({"error": "invalid JSON body", "detail": str(e)}, status=400)
        return view(request, *args, **kwargs)
    return _wrapped


def enforce_query_identity(view):
    """
        GET
    """
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        claims = getattr(request, "claims", None)
        if not claims:
            return JsonResponse({"error": "token required"}, status=401)

        qd = request.GET.copy()
        utype = str(claims.get("user_type", "1"))

        uid = claims.get("user_id")
        if not uid and uid != 0:
            return JsonResponse({"error": "user_id missing in token"}, status=403)

        if qd.get("user_id") and qd.get("user_id") != str(uid):
            return JsonResponse({"error": "Forbidden: user_id mismatch"}, status=403)

        qd["user_id"] = str(uid)

        if utype == "0":
            mid = claims.get("merchant_id")
            if not mid and mid != 0:
                return JsonResponse({"error": "merchant_id missing in token"}, status=403)


            if qd.get("merchant_id") and qd.get("merchant_id") != str(mid):
                return JsonResponse({"error": "Forbidden: merchant_id mismatch"}, status=403)

            qd["merchant_id"] = str(mid)
        #     if "user_id" in qd:
        #         qd.pop("user_id", None)
        #
        # else:
        #     uid = claims.get("user_id")
        #     if not uid and uid != 0:
        #         return JsonResponse({"error": "user_id missing in token"}, status=403)
        #
        #     if qd.get("user_id") and qd.get("user_id") != str(uid):
        #         return JsonResponse({"error": "Forbidden: user_id mismatch"}, status=403)
        #
        #     qd["user_id"] = str(uid)


        request.GET = qd

        request.enforced_scope = {
            "user_type": int(utype) if utype.isdigit() else None,
            "merchant_id": claims.get("merchant_id"),
            "user_id": claims.get("user_id"),
        }
        return view(request, *args, **kwargs)
    return _wrapped