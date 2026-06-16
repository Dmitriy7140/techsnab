from django import forms


class RequestForm(forms.Form):
    """Заявка на расчёт стоимости перевозки."""

    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}),
    )
    phone = forms.CharField(
        max_length=40,
        widget=forms.TextInput(attrs={'placeholder': '+7 (___) ___-__-__'}),
    )
    cargo = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Что везём (перекись, каустик, кислота…)'}
        ),
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Маршрут, объём, сроки', 'rows': 3}
        ),
    )
