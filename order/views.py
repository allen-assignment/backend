from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Order, OrderItem
from user.models import User
from menu.models import MenuItem
import json



# Create your views here.

# Add new order
@csrf_exempt
@require_http_methods(['POST'])
def new_order(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        table_number = data.get('table_number')
        items = data.get('items')

        if not user_id or not items or not table_number:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

        order = Order.objects.create(user=user, table_number = table_number, status= 0, total_price=0)

        total_price = 0
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
        order.total_price = total_price
        order.save()

        return JsonResponse({
            'message': 'Order created successfully',
            'order_id': order.id,
            'total_price':float(order.total_price)
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_all_orders(request):
    try:
        user_id = request.GET.get('user_id')
        if user_id:
            orders = Order.objects.filter(user_id=user_id)
        else:
            orders = Order.objects.all()

        orders = orders.select_related('user').prefetch_related('items__item').order_by('-created_at')

        data = []
        for order in orders:
            items_data = []
            for order_item in order.items.all():
                items_data.append({
                    'item_id': order_item.item.id,
                    'name': order_item.item.name,

                    'quantity': order_item.quantity,
                    'item_price': float(order_item.item_price),
                    'subtotal': float(order_item.subtotal)
                })

            data.append({
                'order_id': order.id,
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


# Update order status to cancelled
@csrf_exempt
@require_http_methods(["POST"])
def cancel_order(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')

        if not order_id:
            return JsonResponse({'error': 'Order not existed'}, status=400)

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)

        order.status = 1  # which mean order cancelled
        order.save()

        return JsonResponse({'message': 'Order canceled successfully'}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    except Exception as e:
        return JsonResponse({'error': 'str(e)'}, status=500)