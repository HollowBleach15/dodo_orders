from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Branch(models.Model):
    name = models.CharField("Название", max_length=120)
    address = models.CharField("Адрес", max_length=255)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"

    def __str__(self):
        return self.name


class Product(models.Model):
    CATEGORY_CHOICES = [
        ("pizza", "Пицца"),
        ("drink", "Напиток"),
        ("extra", "Дополнительно"),
    ]
    name = models.CharField("Название", max_length=120)
    category = models.CharField("Категория", max_length=16, choices=CATEGORY_CHOICES)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Client(models.Model):
    CLIENT_TYPE_CHOICES = [
        ("retail", "Розничный"),
        ("corporate", "Корпоративный"),
        ("franchisee", "Франчайзи"),
    ]
    # Автоматическая скидка по типу (применяется в OrderService)
    CLIENT_DISCOUNT_MAP = {
        "retail": Decimal("0"),
        "corporate": Decimal("5"),
        "franchisee": Decimal("10"),
    }

    client_type = models.CharField(
        "Тип клиента", max_length=16, choices=CLIENT_TYPE_CHOICES, default="retail"
    )
    orders: "models.Manager[Order]"
    full_name = models.CharField("ФИО / Название", max_length=200)
    phone = models.CharField("Телефон", max_length=32, unique=True)
    email = models.EmailField("Email", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    @property
    def default_discount(self) -> Decimal:
        return self.CLIENT_DISCOUNT_MAP.get(self.client_type, Decimal("0"))

    @property
    def orders_count(self):
        return self.orders.count()

    @property
    def last_order_date(self):
        last = self.orders.order_by("-created_at").first()
        return last.created_at if last else None


class Order(models.Model):
    items: "models.Manager[OrderItem]"
    STATUS_CHOICES = [
        ("new", "Новый"),
        ("in_work", "В работе"),
        ("done", "Выполнен"),
        ("cancelled", "Отменён"),
    ]
    TYPE_CHOICES = [
        ("delivery", "Доставка"),
        ("pickup", "Самовывоз"),
        ("dine_in", "В зале"),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="orders", verbose_name="Клиент")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders", verbose_name="Филиал")
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Оператор")
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default="new")
    order_type = models.CharField("Тип заказа", max_length=16, choices=TYPE_CHOICES, default="delivery")
    discount_percent = models.DecimalField("Скидка, %", max_digits=5, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField("Итого", max_digits=12, decimal_places=2, default=Decimal("0"))
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Заказ #{self.pk} ({self.get_status_display()})"

    def recalc_total(self):
        subtotal = sum((i.line_total for i in self.items.all()), Decimal("0"))
        discount = subtotal * (self.discount_percent / Decimal("100"))
        self.total = (subtotal - discount).quantize(Decimal("0.01"))
        return self.total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField("Количество", default=1)
    price = models.DecimalField("Цена за ед.", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    @property
    def line_total(self):
        return (self.price * self.quantity).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.product.price
        super().save(*args, **kwargs)


class UserBranch(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_branches",
        verbose_name="Пользователь"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="user_branches",
        verbose_name="Филиал"
    )

    class Meta:
        unique_together = [("user", "branch")]
        verbose_name = "Доступ к филиалу"
        verbose_name_plural = "Доступы к филиалам"

    def __str__(self):
        return f"{self.user.username} → {self.branch.name}"


User.add_to_class(
    "branches",
    property(lambda self: Branch.objects.filter(user_branches__user=self))
)