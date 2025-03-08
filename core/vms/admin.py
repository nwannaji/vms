from django.contrib import admin
from django import forms
from .models import Employee,Visitor

# Register your models here.
class EmployeeAdmin (admin.ModelAdmin):
    fieldsets =[
        ('EmployeeDetails', {'fields':['employee_id','employee_name','dept_name','unit','email_address','phone_number',
                                       'is_Admin','is_contract_staff']}),
    ]
    readonly_fields = ('date_of_employment',)
    list_display = ('employee_id','employee_name','dept_name','unit','email_address','phone_number','is_Admin',)
    search_fields = ('employee_id','employee_name','dept_name','unit','email_address',)

class VisitorAdmin(admin.ModelAdmin):
    fieldsets = [
        ('VisitorDetails', {'fields':['visitor_name','phone_number','email_address','organization','dept','whom_to_see',
                                      'is_official','is_invited','first_timer','date_of_visit']}),
    ]
    readonly_fields = ('visitor_name','phone_number','email_address','organization','dept','whom_to_see','is_official',
                       'is_invited','first_timer','date_of_visit',)
    list_display = ('visitor_name','phone_number','email_address','organization','dept','is_official','date_of_visit',)
    
    search_fields = ('visitor_name',)
    # form = VisitorForm

admin.site.register(Employee, EmployeeAdmin)
admin.site.register(Visitor,VisitorAdmin)
