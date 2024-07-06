import random
import string
import pandas as pd
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponseRedirect
from django.db.models import Sum
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from .models import Product, Category, UnitOfMeasurement, StockIn, StockOut
from .forms import ExcelUploadForm

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(UnitOfMeasurement)
class UnitOfMeasurementAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'code', 'unit_of_measurement', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('category', 'is_active')
    change_list_template = "admin/product_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel), name='product_upload_excel'),
        ]
        return custom_urls + urls
    
    def upload_excel(self, request):
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['file']
                try:
                    df = pd.read_excel(excel_file)
                    for index, row in df.iterrows():
                        category_name = row['category']
                        category, _ = Category.objects.get_or_create(name=category_name)

                        uom_name = row['unit_of_measurement']
                        uom, _ = UnitOfMeasurement.objects.get_or_create(name=uom_name)

                        product, _ = Product.objects.update_or_create(
                            code=row['code'],
                            defaults={
                                'name': row['name'],
                                'category': category,
                                'unit_of_measurement': uom,
                                'is_active': row['is_active']
                            }
                        )
                    self.message_user(request, "Products uploaded successfully")
                    return HttpResponseRedirect("../")
                except Exception as e:
                    self.message_user(request, f"Error during upload: {str(e)}", level=messages.ERROR)
        else:
            form = ExcelUploadForm()
        
        context = {
            'form': form,
            'title': 'Upload Excel File',
        }
        return render(request, "admin/upload_excel.html", context)

admin.site.register(Product, ProductAdmin)

class StockInAdmin(admin.ModelAdmin):
    list_display = ('product', 'rate', 'quantity', 'batch_id')
    search_fields = ('product__name', 'product__code')

    change_list_template = "admin/stockin_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.upload_excel, name='inventory_stockin_upload_excel'),
        ]
        return custom_urls + urls

    def generate_unique_batch_id(self):
        while True:
            batch_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if not StockIn.objects.filter(batch_id=batch_id).exists():
                return batch_id

    def upload_excel(self, request):
        if request.method == 'POST':
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['file']
                try:
                    df = pd.read_excel(excel_file)
                    for _, row in df.iterrows():
                        product_code = row.get('product_code')
                        product_name = row.get('product_name')
                        rate = row['rate']
                        quantity = row['quantity']
                        batch_id = row.get('batch_id', '')

                        try:
                            rate = float(rate)
                            quantity = float(quantity)
                        except ValueError:
                            messages.error(request, f"Rate and quantity must be decimal numbers. Invalid data: Rate: {rate}, Quantity: {quantity}")
                            return redirect('admin:inventory_stockin_upload_excel')

                        if product_code:
                            product, _ = Product.objects.get_or_create(
                                code=product_code,
                                defaults={'name': product_name or product_code, 'category_id': 1, 'unit_of_measurement_id': 1, 'is_active': True}
                            )
                        elif product_name:
                            product, _ = Product.objects.get_or_create(
                                name=product_name,
                                defaults={'code': product_name, 'category_id': 1, 'unit_of_measurement_id': 1, 'is_active': True}
                            )
                        else:
                            messages.error(request, "Product code or product name is required.")
                            return redirect('admin:inventory_stockin_upload_excel')

                        if not batch_id:
                            batch_id = self.generate_unique_batch_id()
                        else:
                            while StockIn.objects.filter(batch_id=batch_id).exists():
                                batch_id = self.generate_unique_batch_id()

                        try:
                            StockIn.objects.create(
                                product=product,
                                rate=rate,
                                quantity=quantity,
                                batch_id=batch_id
                            )
                        except IntegrityError:
                            messages.error(request, f"Duplicate batch ID found: {batch_id}. Skipping row.")
                            continue

                    messages.success(request, "Stock In data uploaded successfully.")
                    return redirect('admin:inventory_stockin_changelist')
                except Exception as e:
                    messages.error(request, f"Error during upload: {str(e)}")
        else:
            form = ExcelUploadForm()

        return render(request, 'admin/upload_excel.html', {'form': form})

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_excel_url'] = 'admin:inventory_stockin_upload_excel'
        return super().changelist_view(request, extra_context=extra_context)

admin.site.register(StockIn, StockInAdmin)

@admin.register(StockOut)
class StockOutAdmin(admin.ModelAdmin):
    list_display = ('product', 'date_of_disbursement', 'quantity', 'available_quantity')
    search_fields = ('product__name', 'product__code')
    list_filter = ('date_of_disbursement',)
    readonly_fields = ('available_quantity',)

    def available_quantity(self, obj):
        if obj and obj.product:
            total_stock_in = StockIn.objects.filter(product=obj.product).aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_stock_out = StockOut.objects.filter(product=obj.product).aggregate(Sum('quantity'))['quantity__sum'] or 0
            available_stock = total_stock_in - total_stock_out
            return available_stock
        return 'N/A'

    available_quantity.short_description = 'Available Quantity'

    def save_model(self, request, obj, form, change):
        if obj.quantity == 0:
            form.add_error('quantity', _('Null item cannot be checked out.'))
            return
        
        if obj.product_id is None:
            form.add_error('product', _('You cannot check out with a null product.'))
            return
        
        if obj.product_id and not StockIn.objects.filter(product=obj.product_id).exists():
            form.add_error('product', _('Selected product does not have any stock available.'))
            return
        
        total_stock_in = StockIn.objects.filter(product=obj.product).aggregate(Sum('quantity'))['quantity__sum'] or 0
        total_stock_out = StockOut.objects.filter(product=obj.product).aggregate(Sum('quantity'))['quantity__sum'] or 0
        available_stock = total_stock_in - total_stock_out

        if obj.quantity > available_stock:
            form.add_error('quantity', _(f'Insufficient stock for {obj.product.name}. Available: {available_stock}, Requested: {obj.quantity}'))
            return
        
        super().save_model(request, obj, form, change)
