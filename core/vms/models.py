from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth.models import User, Group
from django.utils.timezone import now
from django.db import models

class Employee(models.Model):
    employee_id = models.CharField(unique=True,primary_key=True, max_length=30,null=False)
    employee_name = models.CharField(max_length=200, verbose_name='Employee Name')
    dept_name = models.CharField(max_length=100, verbose_name='Department Name')
    unit = models.CharField(max_length=100, blank=True, null=True)
    date_of_employment = models.DateTimeField(default=now, blank=True, null=True, verbose_name='Date of Employment')
    email_address = models.EmailField(max_length=150, unique=True, verbose_name='Email Address', help_text='Please use your official email address.')
    phone_number = models.CharField(max_length=15, unique=True, help_text='Please type your mobile number.')
    is_Admin = models.BooleanField(default=False, verbose_name='Admin?')
    is_contract_staff = models.BooleanField(default=False, blank=True, null=True, verbose_name='Contract staff?')

    def __str__(self) -> str:
        return self.employee_name
# Signal to automatically create a User and add to "Users" group
@receiver(post_save, sender=Employee)
def create_employee_user(sender, instance, created, **kwargs):
    if created:
        user, user_created =User.objects.get_or_create(
            username=instance.employee_id,
            defaults={'first_name':instance.employee_name.split()[0],
                        'last_name':" ".join(instance.employee_name.split()[1]),
                        'email':instance.email_address}
                                                    )
  # If the user was newly created, set password and group
        if user_created:
            user.set_password("admin123")  # set default password (should be changed later)
            user.save()
        # Assign user to the "Users" group
            group, _ = Group.objects.get_or_create(name='Users')
            user.groups.add(group)

class Visitor(models.Model):
    visitor_id = models.AutoField(primary_key=True)
    visitor_name = models.CharField(max_length=150, verbose_name='Visitor Name')
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="Phone Number", help_text="Phone number")
    email_address = models.EmailField(max_length=200, unique=True, verbose_name='Email Address', help_text='Please provide a valid email address')
    qr_code = models.CharField(max_length=250, blank=True, null=True, verbose_name='QR Code')
    otp = models.IntegerField(default=0, blank=True, null=True)
    organization = models.CharField(max_length=250, blank=True, null=True)
    dept = models.CharField(max_length=150, blank=True, verbose_name='Department(s) to Visit')
    whom_to_see = models.ManyToManyField(Employee, related_name='visitor')
    is_official = models.BooleanField(default=False, verbose_name='Official?')
    comments = models.TextField(blank=True, null=True)
    is_invited = models.BooleanField(default=False, blank=True, null=True, verbose_name="Invited?")
    first_timer = models.BooleanField(default=False, blank=True, null=True, verbose_name='First Timer?')
    date_of_visit = models.DateTimeField(default=now, blank=True, verbose_name='Date of Visit')

    def __str__(self) -> str:
        return self.visitor_name
    
    # Retrieve the names of employees the visitor wants to see.
    def get_employee_name(self):
        return ', '.join([employee.employee_name for employee in self.whom_to_see.all()])
    
    # Retrieve the departments of employees the visitor wants to see.
    def get_department_name(self):
        return ', '.join([employee.dept_name for employee in self.whom_to_see.all()])

class Pending_Visitor(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='Pending_Visitor')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    status_choices = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('CHECKOUT', 'Checkout'),
        ('DECLINED', 'Declined'),
        ('RESCHEDULED', 'Rescheduled'),

    ]
    status = models.CharField(max_length=15, choices=status_choices, default='PENDING')
    scheduled_time = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.name)

class CheckIn_Visitor(models.Model):
    id = models.AutoField(primary_key=True)
    visitor_name = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='CheckIn_Visitor')
    time_In = models.DateTimeField(auto_now_add=True)
    time_Out = models.DateTimeField(null=True, blank=True)  # Manually updated for check-out
    is_pending = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)

    def checkOut(self):
        #Marks the visitor as checkout
        self.time_Out = now()
        self.is_pending = False
        self.save()
    def approve(self, employee):
        #Approves the visittor
        self.is_approved =True
        self.approved_by = employee
        self.is_pending = False
        self.save()
    def __str__(self) -> str:
        return f"Visitor: {self.visitor_name}, Checked In: {self.time_In}, Approved By: {self.approved_by}"

