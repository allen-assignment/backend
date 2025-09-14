from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import MenuItem, MenuCategory
import json, io, csv
from .ocr_function import analyze_layout, parse_to_items, preview_items
# Create your views here.

# Add menu categories
@csrf_exempt
@require_http_methods(['POST'])
def add_menuCategory(request):
    try:
        data = json.loads(request.body)
        category_name = data.get('category_name')
        description = data.get('description')

        if not category_name:
            return JsonResponse({'error': 'category_name cannot be empty'}, status=400)

        category = MenuCategory.objects.create(category_name=category_name, description=description)
        return JsonResponse({'message': 'category created success', 'category_name': category.category_name})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


# Add menu items
@csrf_exempt
@require_http_methods(['POST'])
def add_menuItem(request):
    try:
        data = json.loads(request.body)
        category_id = data.get('category_id')
        image_url = data.get('image_url')
        name = data.get('name')
        price = data.get('price')
        inventory = data.get('inventory')
        description = data.get('description')

        if not category_id or not name or image_url is None or price is None or inventory is None:
            return JsonResponse({'error': 'All fields cannot be empty'}, status=400)

        try:
            category = MenuCategory.objects.get(id=category_id)
        except MenuCategory.DoesNotExist:
            return JsonResponse({'error': 'Category does not exist'}, status=404)

        menuItem = MenuItem.objects.create(
            image_url=image_url,
            name=name,
            price=price,
            inventory=inventory,
            category=category,
            description=description
        )

        return JsonResponse({'message': 'menu item created success', 'name': menuItem.name})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)


# Get all menu items
@csrf_exempt
@require_http_methods(["GET"])
def get_AllMenuItems(request):
    items = MenuItem.objects.select_related('category').all()

    data = []
    for item in items:
        data.append({
            'id': item.id,
            'name': item.name,
            'image_url': item.image_url,
            'price': item.price,
            'inventory': item.inventory,
            'category':{
                'id': item.category.id,
                'name': item.category.category_name
            },
            'description': item.description

        })
    return JsonResponse({'menuItems': data}, status=200)


def _items_to_csv_bytes(items):
    sio = io.StringIO(newline="")
    writer = csv.writer(sio)
    writer.writerow(["Category", "Name", "Price", "Description", "Tags"])
    for it in items:
        writer.writerow([
            it.get("category", ""),
            it.get("name", ""),
            it.get("price", ""),
            it.get("description") or "",
            ",".join(it.get("tags", []) or []),
        ])
    return ("\ufeff" + sio.getvalue()).encode("utf-8")

@csrf_exempt
def menu_ocr_upload(request):
    """
    POST /menu/ocr/upload/
    form-data: file=@menu.jpg | menu.png | menu.pdf
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "file is required"}, status=400)

    try:
        file_bytes = f.read()
        layout = analyze_layout(file_bytes)
        items = parse_to_items(layout)


        wants_csv = (
                request.GET.get("format") == "csv"
                or request.POST.get("format") == "csv"
                or "text/csv" in (request.headers.get("Accept", "") or "")
        )

        if wants_csv:
            csv_bytes = _items_to_csv_bytes(items)
            filename_base = (getattr(f, "name", "menu") or "menu").rsplit(".", 1)[0]
            resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
            resp["Content-Disposition"] = f'attachment; filename="{filename_base}.csv"'
            return resp


        return JsonResponse(
            {"ok": True, "mode": "preview", "items": items},
            status=200,
            json_dumps_params={"ensure_ascii": False},
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


