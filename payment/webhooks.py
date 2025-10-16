# payments/webhooks.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import stripe
from datetime import datetime

stripe.api_key = "sk_test_51SIQi9Jaz9prsnKpN7frpgDoJ7hGFysZhlPxsZ35BRDrvfqlklkUC8dWQDtHoQoSQA4wvKwoaXkdM5gL1leBCFrL00fORDVOHE"
WEBHOOK_SECRET = "whsec_babdc17fbd53897fb1759ede5eb2d57843e96aa7d87451df4d73f8bb1b18a443"

# Simple in-memory counter (for demo)
FAILED_ATTEMPTS = {}

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"error": "Invalid signature"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Log all received events
    event_type = event["type"]
    data = event["data"]["object"]
    print(f"[{datetime.now()}] Stripe event received: {event_type}")

    # Detect failed payments
    if event_type == "payment_intent.payment_failed":
        ip = request.META.get("REMOTE_ADDR", "unknown")
        FAILED_ATTEMPTS[ip] = FAILED_ATTEMPTS.get(ip, 0) + 1
        print(f"Payment failed from {ip}. Count: {FAILED_ATTEMPTS[ip]}")

        # Alert for multiple failures (simple anomaly detection)
        if FAILED_ATTEMPTS[ip] >= 3:
            print(f"Suspicious behavior detected from {ip} - possible fraud attempt!")

    # Successful payment
    elif event_type == "payment_intent.succeeded":
        print(f"Payment succeeded for: {data.get('id')}")

    return JsonResponse({"status": "success"}, status=200)
