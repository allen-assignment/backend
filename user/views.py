from django.db import transaction
import jwt
import datetime
from django.views.decorators.csrf import csrf_exempt

from .models import User, Merchant
from django.http import JsonResponse
from django.contrib.auth.hashers import check_password, make_password
import os
from openai import AzureOpenAI
import requests
import json
# Create your views here.

azure_openai_endpoint = "https://comp6016-openai.openai.azure.com/"
deployment = "text-embedding-3-small"
api_key_azure_openai = "2JLTamBK1Rvyngw4Th4apu7ztsYaPzYGxMyMxnRKKwdyfHQ2pEuEJQQJ99BHACYeBjFXJ3w3AAABACOGVqdb"
SECRET_KEY = "compassignment"

client = AzureOpenAI(
    api_key=api_key_azure_openai,
    api_version="2024-02-01",
    azure_endpoint=azure_openai_endpoint
)

search_endpoint = "https://comp6016-cognitive-search.search.windows.net"
index_name = "dish_item"
api_key_cog_search = "cCg3VoRZL1cMMNvBeg4j5LMH7VKo787y4KkdCZlaTZAzSeAazupM"
search_url = f"{search_endpoint}/indexes/{index_name}/docs/search?api-version=2024-07-01"

@csrf_exempt
def vector_search(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    text_to_search = data.get("text", "")
    top_k = int(data.get("top_k", 3))
    restaurant_id = data.get("restaurant_id", "1")

    if not text_to_search:
        return JsonResponse({"error": "text cannot be null"}, status=400)

    try:

        embedding_response = client.embeddings.create(
            input=[text_to_search],
            model=deployment
        )
        embedding_vector = embedding_response.data[0].embedding


        headers = {
            "Content-Type": "application/json",
            "api-key": api_key_cog_search
        }

        search_payload = {
            "count": True,
            "select": "id, name, text, restaurant_id",
            "filter": f"restaurant_id eq '{restaurant_id}'",
            "vectorFilterMode": "preFilter",
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": embedding_vector,
                    "fields": "embedding",
                    "exhaustive": True,
                    "weight": 0.5,
                    "k": top_k
                }
            ]
        }

        search_resp = requests.post(search_url, headers=headers, json=search_payload)
        search_results = search_resp.json()

        return JsonResponse(search_results, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def user_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return JsonResponse({'error': 'password and username must not be null'}, status=400)

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not existed'}, status=404)

            if check_password(password, user.password):
                payload = {
                    "user_id": user.id,
                    "username": user.username,
                    "user_email": user.email,
                    "user_type": user.usertype,
                    "taste_preferences": user.taste_preferences,
                    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
                }
                token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
                if user.usertype == 0:
                    merchant = Merchant.objects.get(user_id=user.id)
                    payload = {
                        "user_id": user.id,
                        "username": user.username,
                        "user_email": user.email,
                        "merchant_id": merchant.id,
                        "merchant_name": merchant.name,
                        "user_type": user.usertype,
                        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
                    }
                    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
                    return JsonResponse({'message': 'Login success', 'token':token}, status=200)
                return JsonResponse({'message': 'Login success', 'token': token}, status=200)
            else:
                return JsonResponse({'error': 'Incorrect password'}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'error': 'method error'}, status=405)

@csrf_exempt
def user_register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            email = data.get('email')
            birth_date = data.get('birth_date')
            usertype = int(data.get('usertype', 1))
            merchant_name = data.get('merchantName')
            taste_preferences=data.get('tastePreferences')

            if not all([username, password]):
                return JsonResponse({'error': 'username and password must not be null'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'user existed'}, status=400)

            hashed_password = make_password(password)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'invalid JSON'}, status=400)
        try:
            with transaction.atomic():
                user = User.objects.create(
                    username=username,
                    password=hashed_password,
                    email=email,
                    birth_date=birth_date,
                    usertype=usertype,
                    taste_preferences=taste_preferences
                )

                if usertype == 0:
                    if not merchant_name:
                        raise ValueError('merchant_name is required for merchant users')

                    Merchant.objects.create(
                        name=merchant_name,
                        email=email,
                        user_id=user.id
                    )
                return JsonResponse({
                    'message': 'register success',
                    'username': user.username,
                    'user_id': user.id
                })

        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'registration failed', 'detail': str(e)}, status=500)



@csrf_exempt
def get_user_by_id(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id')

        if not user_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)

        try:
            user = User.objects.get(id=user_id)
            return JsonResponse({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'birth_date': user.birth_date,
                'usertype': user.usertype
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

    return JsonResponse({'error': 'method error'}, status=405)

@csrf_exempt
def decode_token(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        token = data.get('token')
        if not token:
            return JsonResponse({'error': 'token is required'}, status=400)
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return JsonResponse({'message': 'Decode success', 'userinfo': decoded}, status=200)
        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'token expired'}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({'error': 'invalid token'}, status=401)
    else:
        return JsonResponse({'error': 'method error'}, status=405)
