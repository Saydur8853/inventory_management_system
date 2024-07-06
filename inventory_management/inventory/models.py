import random
import string
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class UnitOfMeasurement(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True)
    unit_of_measurement = models.ForeignKey(UnitOfMeasurement, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class StockIn(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    date_of_purchase = models.DateField(default=timezone.now)
    quantity = models.IntegerField()
    batch_id = models.CharField(max_length=4, unique=True, default='')
    
    def save(self, *args, **kwargs):
        if not self.batch_id:
            self.batch_id = self.generate_batch_id()
        super().save(*args, **kwargs)

    def generate_batch_id(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    def __str__(self):
        return f"{self.product.name} - {self.batch_id} - {self.quantity}"

class StockOut(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date_of_disbursement = models.DateField(default=timezone.now)
    quantity = models.IntegerField()

    def clean(self):
        total_stock_in = sum(stock_in.quantity for stock_in in StockIn.objects.filter(product=self.product))
        total_stock_out = sum(stock_out.quantity for stock_out in StockOut.objects.filter(product=self.product))
        available_stock = total_stock_in - total_stock_out
        
        if self.quantity > available_stock:
            raise ValidationError(f'Insufficient stock for {self.product.name}. Available: {available_stock}, Requested: {self.quantity}')

    def __str__(self):
        return f"{self.product.code} - {self.quantity} - {self.date_of_disbursement}"