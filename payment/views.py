import json, stripe
import os
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.conf import settings
from .models import Payment, PaymentAttempt
from django.http import JsonResponse


stripe.api_key = settings.STRIPE_SECRET_KEY

def home(request):
    return HttpResponse("Payments App is Working")

def _rate_key(prefix, request):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    user = getattr(request, "user", None)
    uid = str(getattr(user, "id", "")) if user and getattr(user, "is_authenticated", False) else ""
    return f"{prefix}:{uid}:{ip}"

def _too_many(prefix, limit, window_seconds, request):
    key = _rate_key(prefix, request)
    now_bucket = int(timezone.now().timestamp() // window_seconds)
    bucket_key = f"{key}:{now_bucket}"
    count = cache.get(bucket_key, 0) + 1
    cache.set(bucket_key, count, timeout=window_seconds)
    return count > limit

def _log_attempt(request, route, success, reason=""):
    ip = request.META.get("REMOTE_ADDR", None)
    uid = str(getattr(request.user, "id", "")) if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False) else ""
    PaymentAttempt.objects.create(user_id=uid, ip=ip, route=route, success=success, reason=reason)

@csrf_exempt
def create_intent(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    if _too_many("payments:create", 10, 60, request):
        _log_attempt(request, "create-intent", False, "rate_limited")
        return JsonResponse({"error": "Too many attempts. Please wait a minute."}, status=429)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        _log_attempt(request, "create-intent", False, "invalid_json")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    data = json.loads(request.body)
    amount = int(payload.get("amount", 0))
    currency = (payload.get("currency") or "usd").lower()
    order_id = str(payload.get("order_id") or "")
    customer_id = payload.get("customer_id")

    if amount <= 0 or not order_id:
        _log_attempt(request, "create-intent", False, "bad_params")
        return JsonResponse({"error": "amount and order_id required"}, status=400)

    try:
        with transaction.atomic():
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id if customer_id else None,
                automatic_payment_methods={"enabled": True},
            )

            Payment.objects.update_or_create(
                stripe_payment_intent_id=intent["id"],
                defaults={
                    "order_id": order_id,
                    "amount": amount,
                    "currency": currency,
                    "status": intent["status"],
                    "stripe_customer_id": customer_id or "",
                },
            )

        _log_attempt(request, "create-intent", True, "")
        return JsonResponse({"client_secret": intent["client_secret"], "payment_intent_id": intent["id"]})
    except stripe.error.StripeError as e:
        _log_attempt(request, "create-intent", False, "stripe_error")
        return JsonResponse({"error": str(e)}, status=400)
    except Exception:
        _log_attempt(request, "create-intent", False, "server_error")
        return JsonResponse({"error": "Server error"}, status=500)

@csrf_exempt
def webhook(request):
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    payload = request.body
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    type = event["type"]
    data = event["data"]["object"]

    if type in ("payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.processing", "payment_intent.requires_action"):
        pi_id = data["id"]
        status = data.get("status", "")
        failure_code = data.get("last_payment_error", {}).get("code", "")
        failure_message = data.get("last_payment_error", {}).get("message", "")

        card_brand = card_last4 = ""
        try:
            if data.get("latest_charge"):
                ch = stripe.Charge.retrieve(data["latest_charge"])
                pm = ch.get("payment_method_details", {})
                card = pm.get("card", {})
                card_brand = card.get("brand", "") or ""
                card_last4 = card.get("last4", "") or ""
        except Exception:
            pass

        Payment.objects.filter(stripe_payment_intent_id=pi_id).update(
            status=status,
            failure_code=failure_code or "",
            failure_message=failure_message or "",
            card_brand=card_brand,
            card_last4=card_last4,
        )

    return HttpResponse(status=200)
