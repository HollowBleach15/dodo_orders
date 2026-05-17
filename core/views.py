import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse

from .models import Order, Client, Product
from .forms import OrderForm, ClientForm, OrderFilterForm
from .services import OrderService


@login_required
def dashboard(request):
    stats = {
        "orders_total": Order.objects.count(),
        "orders_new": Order.objects.filter(status="new").count(),
        "orders_in_work": Order.objects.filter(status="in_work").count(),
        "clients_total": Client.objects.count(),
    }
    return render(request, "dashboard.html", {"stats": stats})


# ---------- ЗАКАЗЫ ----------

@login_required
def order_list(request):
    qs = Order.objects.select_related("client", "branch").all()
    form = OrderFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data["status"]:
            qs = qs.filter(status=form.cleaned_data["status"])
        if form.cleaned_data["date_from"]:
            qs = qs.filter(created_at__date__gte=form.cleaned_data["date_from"])
        if form.cleaned_data["date_to"]:
            qs = qs.filter(created_at__date__lte=form.cleaned_data["date_to"])
        if form.cleaned_data["client"]:
            c = form.cleaned_data["client"]
            qs = qs.filter(Q(client__full_name__icontains=c) | Q(client__phone__icontains=c))

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "orders/list.html",
                  {"page_obj": page, "filter_form": form})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("client", "branch")
                     .prefetch_related("items__product"),
        pk=pk
    )
    return render(request, "orders/detail.html", {"order": order})


@login_required
def order_create(request):
    return _order_edit(request, order=None)


@login_required
def order_edit(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return _order_edit(request, order=order)


def _order_edit(request, order):
    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        items_json = request.POST.get("items_json", "[]")
        try:
            items_data = json.loads(items_json)
        except json.JSONDecodeError:
            items_data = []

        if form.is_valid() and items_data:
            obj = form.save(commit=False)
            if obj.operator_id is None:           # ← только при создании
                obj.operator = request.user
            try:
                OrderService.save_order_with_items(obj, items_data)
                messages.success(request, f"Заказ #{obj.pk} сохранён.")
                return redirect("order_detail", pk=obj.pk)
            except Exception as e:
                messages.error(request, f"Ошибка сохранения: {e}")
        else:
            if not items_data:
                messages.error(request, "Добавьте хотя бы одну позицию в заказ.")
    else:
        form = OrderForm(instance=order)

    existing_items = []
    if order:
        existing_items = [
            {"product_id": i.product_id, "name": i.product.name,
             "price": float(i.price), "quantity": i.quantity}
            for i in order.items.select_related("product")
        ]
    products = list(
        Product.objects.filter(is_active=True).values("id", "name", "price", "category")
    )
    for p in products:
        p["price"] = float(p["price"])

    return render(request, "orders/form.html", {
        "form": form,
        "order": order,
        "products": products,        # ← отдаём как Python-объекты, см. п. 7
        "existing_items": existing_items,
    })


@login_required
def order_change_status(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    order = get_object_or_404(Order, pk=pk)
    try:
        OrderService.change_status(order, request.POST.get("status"))
        return JsonResponse({"ok": True, "status": order.status})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


# ---------- КЛИЕНТЫ ----------

@login_required
def client_list(request):
    q = request.GET.get("q", "").strip()
    qs = Client.objects.all()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "clients/list.html", {"page_obj": page, "q": q})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    orders = Order.objects.filter(client=client).select_related("branch").all()[:50]
    return render(request, "clients/detail.html", {"client": client, "orders": orders})


@login_required
def client_create(request):
    return _client_edit(request, None)


@login_required
def client_edit(request, pk):
    return _client_edit(request, get_object_or_404(Client, pk=pk))


def _client_edit(request, client):
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Клиент сохранён.")
            return redirect("client_detail", pk=obj.pk)
    else:
        form = ClientForm(instance=client)
    return render(request, "clients/form.html",
                  {"form": form, "client": client})
