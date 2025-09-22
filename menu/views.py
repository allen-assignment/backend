from django.http import JsonResponse, HttpResponse
from django.db import transaction, IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import MenuItem, MenuCategory
import json, io, csv, uuid, hashlib
from django.core.cache import caches
from .ocr_function import analyze_layout, parse_to_items, _price_to_decimal, COMPLIMENTARY_RE, TAG_SET
from decimal import Decimal


# Create your views here.

# Add menu categories
@csrf_exempt
@require_http_methods(['POST'])
def add_menuCategory(request):
    try:
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        category_name = data.get('category_name')
        description = data.get('description')

        if not merchant_id:
            return JsonResponse({'error': 'merchant_id is required'}, status=400)
        if not category_name:
            return JsonResponse({'error': 'category_name cannot be empty'}, status=400)

        category = MenuCategory.objects.create(merchant_id=merchant_id, category_name=category_name, description=description)
        return JsonResponse({'message': 'category created success',  'merchant_id': int(merchant_id), 'category_name': category.category_name},
            status=201)
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


# Modify menu items
@csrf_exempt
@require_http_methods(["POST"])
def update_menuItem(request, item_id=None):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    item_id = item_id or data.get("id") or data.get("item_id")
    if not item_id:
        return JsonResponse({"error": "item_id is required"}, status=400)

    try:
        item = MenuItem.objects.get(id=item_id)
    except MenuItem.DoesNotExist:
        return JsonResponse({"error": "Menu item not found"}, status=404)

    updatable_fields = ["name", "price", "inventory", "image_url", "description"]
    for f in updatable_fields:
        if f in data and data[f] is not None:
            setattr(item, f, data[f])

    if "category_id" in data and data["category_id"] is not None:
        try:
            cat = MenuCategory.objects.get(id=data["category_id"])
        except MenuCategory.DoesNotExist:
            return JsonResponse({"error": "Category does not exist"}, status=404)
        item.category = cat

    if "isAvailable" in data and data["isAvailable"] is not None:
        try:
            v = int(data["isAvailable"])
        except (TypeError, ValueError):
            return JsonResponse({"error": "isAvailable must be 0 or 1"}, status=400)
        if v not in (0, 1):
            return JsonResponse({"error": "isAvailable must be 0 or 1"}, status=400)
        try:
            item.isAvailable = bool(v)
        except Exception:
            item.isAvailable = v

    item.save()
    return JsonResponse({"message": "menu item updated", "id": item.id}, status=200)


# Delete item
@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def delete_menuItem(request, item_id=None):
    data = {}
    if request.method == "DELETE" and request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
    elif request.method == "POST":
        try:
            data = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid JSON"}, status=400)

    item_id = item_id or data.get("id") or data.get("item_id") or request.GET.get("id")
    if not item_id:
        return JsonResponse({"error": "item_id is required"}, status=400)

    try:
        item = MenuItem.objects.get(id=item_id)
    except MenuItem.DoesNotExist:
        return JsonResponse({"error": "Menu item not found"}, status=404)

    item.delete()
    return JsonResponse({"message": "menu item deleted", "id": int(item_id)}, status=200)


# Get all menu items
@csrf_exempt
@require_http_methods(["GET"])
def get_AllMenuItems(request):
    merchant_id = request.GET.get("merchant_id")
    if not merchant_id:
        return JsonResponse({"error": "merchant_id is required"}, status=400)

    try:
        mid = int(merchant_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "merchant_id must be an integer"}, status=400)

    qs = (
        MenuItem.objects
        .select_related("category")
        .filter(category__merchant_id=mid)
        .order_by("id")
    )

    data = [{
        "id": it.id,
        "name": it.name,
        "image_url": it.image_url,
        "price": str(it.price),
        "inventory": it.inventory,
        "category": {
            "id": it.category_id,
            "name": it.category.category_name,
        },
        "merchant_id": it.category.merchant_id,
        "description": it.description or "",
    } for it in qs]

    return JsonResponse({
        "merchant_id": mid,
        "count": len(data),
        "menuItems": data
    }, status=200)


# def _items_to_csv_bytes(items):
#     sio = io.StringIO(newline="")
#     writer = csv.writer(sio)
#     writer.writerow(["Category", "Name", "Price", "Description", "Tags"])
#     for it in items:
#         writer.writerow([
#             it.get("category", ""),
#             it.get("name", ""),
#             it.get("price", ""),
#             it.get("description") or "",
#             ",".join(it.get("tags", []) or []),
#         ])
#     return ("\ufeff" + sio.getvalue()).encode("utf-8")

cache = caches["ocr_preview"]
PREVIEW_TTL = 900


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
        preview_id = f"pv{uuid.uuid4().hex[:8]}"

        cache.set(preview_id, {"status": "PENDING", "items": items}, timeout=PREVIEW_TTL)

        # wants_csv = (
        #         request.GET.get("format") == "csv"
        #         or request.POST.get("format") == "csv"
        #         or "text/csv" in (request.headers.get("Accept", "") or "")
        # )
        #
        # if wants_csv:
        #     csv_bytes = _items_to_csv_bytes(items)
        #     filename_base = (getattr(f, "name", "menu") or "menu").rsplit(".", 1)[0]
        #     resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
        #     resp["Content-Disposition"] = f'attachment; filename="{filename_base}.csv"'
        #     return resp


        return JsonResponse(
            {"preview_id": preview_id, "items": items},
            status=200,
            # json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def _tags_to_features(tags):
    if not tags:
        return (None, None, None)
    uniq = []
    for t in tags:
        t = (t or '').strip().upper()
        if t and t in TAG_SET and t not in uniq:
            uniq.append(t)
        if len(uniq) == 3:
            break
    return (
        uniq[0] if len(uniq) > 0 else None,
        uniq[1] if len(uniq) > 1 else None,
        uniq[2] if len(uniq) > 2 else None,
    )


@csrf_exempt
@require_http_methods(["GET"])
def ocr_preview_get(request, preview_id: str):
    """
    GET /menu/ocr/preview/<preview_id>/
    """
    data = cache.get(preview_id)
    if not data:
        return JsonResponse({"error": "preview expired or not found"}, status=410)
    return JsonResponse({"preview_id": preview_id, **data}, status=200)



# Ocr Json store to database
@csrf_exempt
@require_http_methods(["POST"])
def ocr_import(request):
    """
    POST /menu/ocr/import/
    Body(JSON):
    {
      "merchant_id": 15,
      "preview_id": "pvxxxxxxx",
      // choose. if return all items from frontend
      "items": [ {category,name,price,description,tags,inventory?}, ... ]
    }
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    merchant_id = payload.get("merchant_id")
    preview_id = payload.get("preview_id")
    items = payload.get("items")  # 可选

    if merchant_id is None:
        return JsonResponse({"error": "merchant_id is required"}, status=400)
    try:
        mid = int(merchant_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "merchant_id must be an integer"}, status=400)

    if not items:
        if not preview_id:
            return JsonResponse({"error": "preview_id or items is required"}, status=400)
        data = cache.get(preview_id)
        if not data:
            return JsonResponse({"error": "preview expired or not found"}, status=410)
        items = data.get("items") or []

    if not isinstance(items, list) or not items:
        return JsonResponse({"error": "items must be a non-empty list"}, status=400)


    cat_cache = {}
    created_cats = 0
    created_items = 0

    try:
        with transaction.atomic():
            for obj in items:

                raw_cat = (obj.get("category") or obj.get("category_name") or "UNCATEGORIZED").strip() or "UNCATEGORIZED"
                ck = raw_cat.lower()

                category = cat_cache.get(ck)
                if category is None:
                    category = MenuCategory.objects.create(
                        merchant_id=mid,
                        category_name=raw_cat,
                        description="",
                    )
                    cat_cache[ck] = category
                    created_cats += 1


                name = (obj.get("name") or "").strip()
                if not name:
                    continue

                price_text = (obj.get("price") or "").strip()
                if COMPLIMENTARY_RE.search(price_text):
                    price_dec = Decimal("0.00")
                else:
                    price_dec = _price_to_decimal(price_text)

                desc = (obj.get("description") or "").strip() or None
                f1, f2, f3 = _tags_to_features(obj.get("tags") or [])

                inventory = 10
                MenuItem.objects.create(
                    category=category,
                    name=name,
                    price=price_dec,
                    description=desc,
                    feature_one=f1,
                    feature_two=f2,
                    feature_three=f3,
                    inventory=inventory,
                    isAvailable=True,
                    # image_url
                )
                created_items += 1


            if preview_id:
                cache.delete(preview_id)

        return JsonResponse({
            "ok": True,
            "merchant_id": mid,
            "categories_created": created_cats,
            "items_created": created_items,
            "total_parsed": len(items)
        }, status=200)

    except IntegrityError as ie:

        return JsonResponse({"ok": False, "error": f"DB constraint: {ie}"}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)




