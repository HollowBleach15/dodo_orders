# Dodo Orders — учёт заказов франчайзинговой пиццерии

Django 5 + DRF + PostgreSQL + Celery (Redis) + JWT.

## Стек
- Python 3.12, Django 5.0, DRF 3.15, SimpleJWT
- PostgreSQL 16, Redis 7
- Celery + django-celery-beat (периодические задачи)
- openpyxl (Excel-отчёты)

## Структура
- `core/` — заказы, клиенты, товары, филиалы (модели, API, веб-UI)
- `reports/` — аналитика выручки/товаров/клиентов
- `dodo_orders/` — настройки проекта

## Запуск
```bash
cp .env.example .env
docker compose up --build
```

## Тесты
```bash
docker compose exec web python manage.py test
```