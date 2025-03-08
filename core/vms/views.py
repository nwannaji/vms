from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.db.models import Count
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from .utils import send_employee_whatsApp_message, send_visitor_whatsApp_message_with_qrCode, send_visitor_whatsApp_message_without_qrCode, generate_qr_code, send_visitor_whatsapp_message_reschedule, upload_qr_code_to_firebase
from .models import CheckIn_Visitor, Pending_Visitor, Visitor, Employee

#@login_required(login_url='/admin/login/')
def dashboard(request):
    """Displays all visitors with associated employees and departments."""
    visitors = Visitor.objects.all().order_by('-visitor_id')
    visitor_data_list = []
    for visitor in visitors:
    # Retrieve the visitor's status from Pending_Visitor
        pending_visit = Pending_Visitor.objects.filter(name=visitor).first()
        visitor_status = pending_visit.status if pending_visit else "UNKNOWN"
        # Assign color codes based on status
        status_colors = {
            "PENDING": "yellow",
            "APPROVED": "green",
            "CHECKOUT": "red",
        }
        status_color = status_colors.get(visitor_status, "gray")  # Default to gray if unknown
        date_of_visit = visitor.date_of_visit
        datetime_format = '%Y-%m-%d %H:%M %p'
        visitor_data_list.append({
            'visitor_name': visitor.visitor_name,
            'organization': visitor.organization,
            'employee_names': ', '.join([employee.employee_name for employee in visitor.whom_to_see.all()]),
            'dept_names': ', '.join([employee.dept_name for employee in visitor.whom_to_see.all()]),
            'is_official': visitor.is_official,
            'is_invited': visitor.is_invited,
            'first_timer': visitor.first_timer,
            'date_of_visit': date_of_visit.strftime(datetime_format),
            'status': visitor_status,  # Include the status in the dashboard data
            'status_color': status_color,  # Include color for template
        })
    context = {'visitor_data_list': visitor_data_list}
    return render(request, 'dashboard.html', context)

def fetch_employees(request):
    query = request.GET.get('q', '')
    if query:
        # Filter employees based on the search query
        employees = Employee.objects.filter(employee_name__icontains=query).values('employee_name', 'dept_name')
        employee_list = [{'name': emp['employee_name'], 'dept': emp['dept_name']} for emp in employees]
        return JsonResponse(employee_list, safe=False)
    return JsonResponse([], safe=False)

@csrf_protect
def get_department_data(request):
    """Fetches visitor count per department."""
    data = Visitor.objects.values('dept').annotate(count=Count('visitor_id')).order_by('dept')
    department_data = {item['dept']: item['count'] for item in data}
    return JsonResponse(department_data)

@csrf_protect
#@login_required(login_url='/admin/login/')
def schedule_visit(request):
    """Handles visitor scheduling, QR generation, and pending approval."""
    if request.method == 'POST':
        is_official = request.POST.get('is_official') =='on'
        is_invited = request.POST.get('invited') =='on'
        first_timer = request.POST.get('first_timer') =='on'
        
        get_employee_name = request.POST.get('whom_to_see')
        employee = get_object_or_404(Employee, employee_name=get_employee_name)

        visitor_data = {
            'visitor_name': request.POST.get('visitor_name'),
            'phone_number': request.POST.get('phone_number'),
            'email_address': request.POST.get('email_address'),
            'qr_code': request.POST.get('qr_code'),
            'otp': request.POST.get('otp'),
            'organization': request.POST.get('organization'),
            'dept': request.POST.get('dept'),
            'is_official': is_official,
            'comments': request.POST.get('comments'),
            'is_invited': is_invited,
            'first_timer': first_timer,
            'date_of_visit': request.POST.get('date_of_visit'),
        }
        visitor = Visitor.objects.create(**visitor_data)
        visitor.whom_to_see.add(employee)
        visitor.date_of_visit = visitor.date_of_visit or now()

        qr_code_path = generate_qr_code(visitor, employee.employee_name)
        qr_code_url = upload_qr_code_to_firebase(qr_code_path, qr_code_path)

        send_visitor_whatsApp_message_without_qrCode(visitor)
        send_employee_whatsApp_message(employee, visitor)

        Pending_Visitor.objects.create(name=visitor, employee=employee, status='PENDING')

        messages.success(request, 'Visitor successfully created.')
        return redirect(reverse('dashboard'))
    
    return render(request, 'schedule_visit.html')

@csrf_protect
@login_required(login_url='/admin/login/')
def check_in(request):
    """Manages visitor check-in actions (approve, checkout, decline)."""
    user = request.user
    employee = get_object_or_404(Employee,employee_id=user.username)
    if request.method == 'POST':
        visitor_id = request.POST.get('visitor_id')
        action = request.POST.get('action')
        reschedule_datetime = request.POST.get('reschedule_datetime')

        visitor = get_object_or_404(Visitor, pk=visitor_id)
        pending_visit = Pending_Visitor.objects.filter(name=visitor).first()
         # Check if this pending visit belongs to the logged-in employee if it's still pending.
        if pending_visit and pending_visit.status == 'PENDING' and pending_visit.employee != employee:
            messages.error(request, "You are not authorized to modify thiS request.")
            return redirect('checkIn')
        check_in, _ = CheckIn_Visitor.objects.get_or_create(visitor_name=visitor,approved_by=employee)
        
        if pending_visit:
            if action == 'approve':
                pending_visit.status = 'APPROVED'
                check_in.is_approved = True
                check_in.is_pending = False
                send_visitor_whatsApp_message_with_qrCode(visitor)
                messages.success(request, f"Visitor {visitor.visitor_name}'s visit has been approved.")

            elif action == 'checkout':
                pending_visit.status = 'CHECKOUT'
                check_in.is_pending = False
                check_in.time_Out = now()  # Set time_out during checkout
                messages.success(request, f"Visitor {visitor.visitor_name} has checked out.")

            elif action == 'decline':
                pending_visit.status = 'DECLINED'
                check_in.is_approved = False
                check_in.is_pending = False
                messages.warning(request, f"Visitor {visitor.visitor_name}'s visit has been declined.")
            
            elif action == 'reschedule_datetime' and reschedule_datetime:
                # Parse the incoming datetime string; adjust the format if necessary.
                # The typical format for a datetime-local input is: "YYYY-MM-DDTHH:MM"
                new_datetime = datetime.strptime(reschedule_datetime, "%Y-%m-%dT%H:%M")
                pending_visit.scheduled_time = new_datetime
                pending_visit.status = 'RESCHEDULED'
                send_visitor_whatsapp_message_reschedule(visitor, new_datetime)
                formatted_datetime = new_datetime.strftime('%Y-%m-%d %I:%M %p')
                messages.info(request, f"Visitor {visitor.visitor_name}'s visit has been rescheduled to {formatted_datetime}.")
            pending_visit.save()
            check_in.approved_by = employee
            check_in.save()
            return redirect('checkIn')
    
    context = {
        'approved_visitors':Pending_Visitor.objects.filter(status='APPROVED',employee=employee),
        'pending_visitors': Pending_Visitor.objects.filter(status='PENDING'),
        'checkout_visitors':Pending_Visitor.objects.filter(status='CHECKOUT'),
    }
    return render(request, 'check_in.html', context)

@csrf_protect
@login_required(login_url='/admin/login/')
def update_date_of_visit(request,visitor_id):
    visitor = get_object_or_404(Visitor, pk=visitor_id)
    if request.method =='POST':
        new_datetime = request.POST.get('reschedule_datetime')
        if new_datetime:
            visitor.date_of_visit = new_datetime
        visitor.save()
        messages.success(request, f"Visitor {visitor.visitor_name}'s details updated successfully.")
        return redirect('check_in')

@csrf_protect
@login_required(login_url='/admin/login/')
def update_checkin_visitor(request, visitor_id):
    """Efficiently updates the CheckIn_Visitor model with timestamps."""
    visitor = get_object_or_404(Visitor, id=visitor_id)
    checkIn = CheckIn_Visitor.objects.create(visitor=visitor)
    messages.success(request, f"{visitor.visitor_name} checked successfully.")
    return redirect('check_in')

@login_required(login_url='/admin/login/')
def approve_visitor(request,checkIn_id, employee_id):
    #Handles visitor approval by an employee
    checkIn = get_object_or_404(CheckIn_Visitor, id=checkIn_id)
    employee = get_object_or_404(Employee, id=employee_id)
    if check_in.is_approved:
        messages.warning(request,"Visitor is already approved.")
    else:
        check_in.approve(employee)
        messages.success(request,f"Visitor{checkIn.visitor_name} approved by{employee.employee_name}")
    return redirect('check_in')

@login_required(login_url='/admin/login/')
def checkout_visitor(request,checkIn_id):
    #Handles Visitor's checkout
    checkIn = get_object_or_404(CheckIn_Visitor, id = checkIn_id)
    if checkIn.time_Out:
        messages.warning(request,"Visitor already checked out")
    else:
        checkIn.checkOut()
        messages.success(request, f"{checkIn.visitor_name} checked out successfully.")
    return redirect('check_in')


@csrf_protect
def draw_chart(request):
    """Displays the chart page."""
    return render(request, 'my_chart.html')

@csrf_protect
def contact_page(request):
    """Renders the contact page."""
    return render(request, 'contact_us.html')

    

