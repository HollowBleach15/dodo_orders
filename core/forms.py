from django import forms
from .models import Order, Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["full_name", "phone", "email", "address", "client_type", "is_active"]
        widgets = {
            **{f: forms.TextInput(attrs={"class": "form-control"})
               for f in ["full_name", "phone", "email", "address"]},
            "client_type": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["client", "branch", "status", "order_type", "discount_percent", "comment"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-select"}),
            "branch": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "order_type": forms.Select(attrs={"class": "form-select"}),
            "discount_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class OrderFilterForm(forms.Form):
    status = forms.ChoiceField(
        required=False,
        choices=[("", "— Все статусы —")] + Order.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(
        attrs={"class": "form-control", "type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(
        attrs={"class": "form-control", "type": "date"}))
    client = forms.CharField(required=False, widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "ФИО или телефон"}))