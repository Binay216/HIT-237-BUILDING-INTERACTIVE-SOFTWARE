from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from .models import RepairRequest
from .forms import RepairRequestForm


def home(request):
    return render(request, 'home.html')


def create_request(request):
    if request.method == 'POST':
        form = RepairRequestForm(request.POST)
        if form.is_valid():
            repair = form.save(commit=False)
            repair.tenant = request.user
            repair.save()
            return redirect('my_requests')
    else:
        form = RepairRequestForm()

    return render(request, 'create_request.html', {'form': form})

def my_requests(request):
    requests = RepairRequest.objects.filter(tenant=request.user).order_by('-created_at')
    return render(request, 'my_requests.html', {'requests': requests})


def edit_request(request, id):
    repair = get_object_or_404(RepairRequest, id=id)

    if request.method == 'POST':
        repair.title = request.POST.get('title')
        repair.description = request.POST.get('description')
        repair.location = request.POST.get('location')
        repair.issue_type = request.POST.get('issue_type')
        repair.priority = request.POST.get('priority')
        repair.save()
        return redirect('my_requests')

    return render(request, 'edit_request.html', {'repair': repair})
def delete_request(request, id):
    repair = get_object_or_404(RepairRequest, id=id)
    repair.delete()
    return redirect('my_requests')
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {'error': 'Username already exists'})

        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('home')

    return render(request, 'register.html')


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


def user_logout(request):
    logout(request)
    return redirect('home')