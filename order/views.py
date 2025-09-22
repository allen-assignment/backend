from decimal import Decimal

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Order, OrderItem
from user.models import User
from menu.models import MenuItem
import json



# Create your views here.

# Add a new order for user on the current merchant
@csrf_exempt
@require_http_methods(['POST'])
def new_order(request):
    try:
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        user_id = data.get('user_id')
        table_number = data.get('table_number')
        items = data.get('items')

        if not merchant_id or not user_id or not items or not table_number:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

        order = Order.objects.create(merchant_id=merchant_id, user=user, table_number = table_number, status= 0, total_price=Decimal('0.00'))

        total_price = Decimal('0.00')
        for item in items:
            item_id = item.get('item_id')
            quantity = int(item.get('quantity',1))

            try:
                menu_item = MenuItem.objects.get(id= item_id)
            except MenuItem.DoesNotExist:
                return JsonResponse({'error': 'Menu item not found'}, status=404)

            item_price = menu_item.price
            subtotal = item_price * quantity
            total_price += subtotal

            OrderItem.objects.create(
                order=order,
                item=menu_item,
                item_price=item_price,
                quantity=quantity,
                subtotal=subtotal
            )
        tax_rate = Decimal('0.02')
        tax_amount = total_price * tax_rate
        total_price += tax_amount

        order.total_price = total_price
        order.save()

        return JsonResponse({
            'message': 'Order created successfully',
            'order_id': order.id,
            'merchant_id': merchant_id,
            'tax': float(tax_amount),
            'total_price': float(order.total_price)
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Get specific merchant order information
# Get specific user order information on current merchant
@csrf_exempt
@require_http_methods(["GET"])
def get_all_orders(request):
    try:
        user_id = request.GET.get('user_id')
        merchant_id = request.GET.get("merchant_id")
        order_id = request.GET.get("order_id")
        if not (user_id or merchant_id or order_id):
            return JsonResponse({"error": "user_id or merchant_id or order_id is required"}, status=400)

        qs = Order.objects.all()

        if user_id:
            try:
                uid = int(user_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "user_id must be an integer"}, status=400)
            qs = qs.filter(user_id=uid)

        if merchant_id:
            try:
                mid = int(merchant_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "merchant_id must be an integer"}, status=400)
            qs = qs.filter(merchant_id=mid)

        if order_id:
            try:
                oid = int(order_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "order_id must be an integer"}, status=400)
            qs = qs.filter(id=oid)

        qs = qs.select_related("user").prefetch_related("items__item").order_by("-created_at")

        if order_id:
            order = qs.first()
            if not order:
                return JsonResponse({"error": "Order not found"}, status=404)

            items_data = [{
                "item_id": oi.item.id,
                "name": oi.item.name,
                "quantity": oi.quantity,
                "item_price": float(oi.item_price),
                "subtotal": float(oi.subtotal),
            } for oi in order.items.all()]

            return JsonResponse({
                "order": {
                    "order_id": order.id,
                    "merchant_id": order.merchant_id,
                    "user_id": order.user.id,
                    "user_name": order.user.username,
                    "table_number": order.table_number,
                    "status": order.get_status_display(),
                    "total_price": float(order.total_price),
                    "order_time": order.order_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "items": items_data
                }
            }, status=200)

        data = []
        for order in qs:
            items_data = [{
                "item_id": oi.item.id,
                "name": oi.item.name,
                "quantity": oi.quantity,
                "item_price": float(oi.item_price),
                "subtotal": float(oi.subtotal),
            } for oi in order.items.all()]

            data.append({
                    'order_id': order.id,
                    'merchant_id': order.merchant_id,
                    'user_id': order.user.id,
                    'user_name': order.user.username,
                    'table_number':order.table_number,
                    'status': order.get_status_display(),
                    'total_price': float(order.total_price),
                    'order_time': order.order_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'items': items_data
                })

        return JsonResponse({'orders': data}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Update order status to cancelled = 0 or Paid =2
@csrf_exempt
@require_http_methods(["POST"])
def cancel_order(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    merchant_id = data.get('merchant_id')
    order_id = data.get('order_id')
    status_val = data.get('status')

    if not order_id:
        return JsonResponse({'error': 'Order not existed'}, status=400)

    if order_id is None or merchant_id is None:
        return JsonResponse({"error": "order_id and merchant_id are required"}, status=400)


    try:
        mid = int(merchant_id)
        oid = int(order_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'order_id and merchant_id must be integers'}, status=400)

    if status_val is None:
        new_status = 1
    else:
        try:
            new_status = int(status_val)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'status must be an integer'}, status=400)

    try:
        order = Order.objects.get(id=oid, merchant_id=mid)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

    order.status = new_status  # 1 = cancelled , 2 = Paid , 0 - submitted
    order.save(update_fields=["status"])

    return JsonResponse({'message': 'Order canceled successfully', 'order_id': order.id}, status=200)
