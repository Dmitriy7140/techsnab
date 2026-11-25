import re
from uuid import uuid4

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Lead
from .reviews.models import Review


class RussianDateField(forms.DateField):
    def __init__(self, **kwargs):
        super().__init__(input_formats=['%d.%m.%Y'], widget=forms.DateInput(
            format='%d.%m.%Y', attrs={'placeholder': 'дд.мм.гггг', 'maxlength': '10',
                                      'pattern': r'[0-9]{2}\.[0-9]{2}\.[0-9]{4}'}),
            error_messages={'invalid': 'Введите дату в формате дд.мм.гггг.'}, **kwargs)

    def to_python(self, value):
        if isinstance(value, str) and value and not re.fullmatch(r'[0-9]{2}\.[0-9]{2}\.[0-9]{4}', value.strip()):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(value)


class ReviewForm(forms.Form):
    submission_id = forms.UUIDField(required=False, initial=uuid4, widget=forms.HiddenInput)
    name = forms.CharField(label='Имя', max_length=120, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    rating = forms.TypedChoiceField(label='Оценка', coerce=int, choices=[(n, str(n)) for n in range(1, 6)])
    comment = forms.CharField(label='Комментарий', max_length=10000, widget=forms.Textarea(attrs={'rows': 4}))

    def save(self, *, submitted_at, review_date, **moderation):
        data = self.cleaned_data
        return Review.objects.get_or_create(
            submission_id=data['submission_id'] or uuid4(),
            defaults={'name': data['name'], 'rating': data['rating'], 'comment': data['comment'],
                      'submitted_at': submitted_at, 'review_date': review_date, **moderation},
        )


class ManagerReviewForm(ReviewForm):
    submission_id = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    review_date = RussianDateField(label='Дата отзыва', initial=timezone.localdate)


class LeadUpdateForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = Lead
        fields = ['status', 'note', 'revision']
        widgets = {'note': forms.Textarea(attrs={'rows': 5})}


class ManagerLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise self.get_invalid_login_error()


class RequestForm(forms.Form):
    """Заявка на расчёт стоимости перевозки."""

    submission_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
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
        max_length=10000,
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Маршрут, объём, сроки', 'rows': 3}
        ),
    )
