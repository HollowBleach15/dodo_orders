from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from openpyxl import Workbook

from core.models import Branch, Order
from .services import RevenueReport, ProductReport, ClientReport
from .export import order_to_excel


def _parse_dates(request):
    today = date.today()
    df = request.GET.get("date_from") or (today - timedelta(days=30)).isoformat()
    dt = request.GET.get("date_to") or today.isoformat()
    return date.fromisoformat(df), date.fromisoformat(dt)


@login_required
def index(request):
    return render(request, "reports/index.html")


@login_required
def revenue(request):
    df, dt = _parse_dates(request)
    branch_id = request.GET.get("branch") or None
    summary = RevenueReport.daily_revenue(df, dt, branch_id)
    by_day = RevenueReport.revenue_by_day(df, dt)
    by_branch = RevenueReport.revenue_by_branch(df, dt)
    cancellation = ClientReport.cancellation_rate(df, dt)

    chart_data = {
        "by_day": {
            "labels": [r["day"].strftime("%d.%m") for r in by_day],
            "revenue": [float(r["revenue"] or 0) for r in by_day],
            "orders": [r["orders"] for r in by_day],
        },
        "by_branch": {
            "labels": [r["branch__name"] for r in by_branch],
            "revenue": [float(r["revenue"] or 0) for r in by_branch],
        },
    }

    return render(request, "reports/revenue.html", {
        "date_from": df, "date_to": dt,
        "summary": summary, "by_day": by_day,
        "by_branch": by_branch, "cancellation": cancellation,
        "branches": Branch.objects.all(),
        "selected_branch": int(branch_id) if branch_id else None,
        "chart_data": chart_data,
    })


@login_required
def products(request):
    df, dt = _parse_dates(request)
    top = ProductReport.top_products(df, dt)
    by_category = ProductReport.revenue_by_category(df, dt)

    category_labels_ru = {"pizza": "Пиццы", "drink": "Напитки", "extra": "Дополнительно"}

    for r in top:
        r["category_display"] = category_labels_ru.get(
            r["product__category"], r["product__category"]
        )

    chart_data = {
        "top": {
            "labels": [r["product__name"] for r in top[:10]],
            "qty": [r["qty_sold"] for r in top[:10]],
        },
        "categories": {
            "labels": [category_labels_ru.get(r["product__category"], r["product__category"])
                       for r in by_category],
            "revenue": [float(r["revenue"] or 0) for r in by_category],
        },
    }

    return render(request, "reports/products.html", {
        "date_from": df, "date_to": dt,
        "top": top, "by_category": by_category,
        "chart_data": chart_data,
    })


@login_required
def clients(request):
    df, dt = _parse_dates(request)
    top = ClientReport.top_clients(df, dt)
    inactive = ClientReport.inactive_clients(60)[:50]

    chart_data = {
        "top": {
            "labels": [r["full_name"] for r in top[:10]],
            "revenue": [float(r["revenue"] or 0) for r in top[:10]],
        },
    }

    return render(request, "reports/clients.html", {
        "date_from": df, "date_to": dt,
        "top": top, "inactive": inactive,
        "chart_data": chart_data,
    })


@login_required
def export_revenue_xlsx(request):
    df, dt = _parse_dates(request)
    by_day = RevenueReport.revenue_by_day(df, dt)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Выручка по дням"
    ws.append(["Дата", "Заказов", "Выручка, ₽"])
    for row in by_day:
        ws.append([row["day"].strftime("%d.%m.%Y"),
                   row["orders"],
                   float(row["revenue"] or 0)])

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="revenue_{df}_{dt}.xlsx"'
    wb.save(resp)
    return resp


@login_required
def order_export_excel(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product").select_related("client", "branch"),
        pk=pk,
    )
    data = order_to_excel(order)
    response = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="order_{order.pk}.xlsx"'
    return response