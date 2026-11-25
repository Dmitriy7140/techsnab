from django.db import models
from django.utils import timezone


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'На модерации'
        APPROVED = 'approved', 'Опубликован'
        REJECTED = 'rejected', 'Отклонён'

    submission_id = models.UUIDField(unique=True, editable=False)
    name = models.CharField(max_length=120)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    review_date = models.DateField()
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    moderated_at = models.DateTimeField(null=True)
    moderated_by = models.CharField(max_length=150, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-submitted_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(rating__range=(1, 5)), name='review_rating_1_to_5')]

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)
