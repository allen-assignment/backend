from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import User
from django.http import JsonResponse
from django.contrib.auth.hashers import check_password, make_password
import json
# Create your views here.
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
                return JsonResponse({'message': 'Login success', 'username': user.username})
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
            usertype = data.get('usertype')

            if not all([username, password]):
                return JsonResponse({'error': 'username and password must not be null'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'user existed'}, status=400)

            hashed_password = make_password(password)

            user = User.objects.create(
                username=username,
                password=hashed_password,
                email=email,
                birth_date=birth_date,
                usertype=usertype
            )

            return JsonResponse({'message': 'register success', 'username': user.username})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'invalid JSON'}, status=400)

    return JsonResponse({'error': 'method error'}, status=405)