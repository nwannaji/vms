from django.contrib.auth.views import LogoutView
from django.urls import path
from .import views



urlpatterns =[
    path('', views.dashboard, name='dashboard'),
    path('schedule_visit/', views.schedule_visit, name='schedule_visit'),
    path('checkIn/', views.check_in , name='checkIn'),
    path('chart/', views.draw_chart, name='chart'),
    path('contact/', views.contact_page, name='contact'),
    path('department-data/', views.get_department_data, name='department_data'),
    path('update-checkIn/', views.update_checkin_visitor, name='update_checkIn'),
    path('update-visit/<int:visitor_id>/', views.update_date_of_visit, name='update_date_of_visit'),
    # path('reschedule/', views.reschedule_visit, name='reschedule_visit'),
    path('fetch_employees/', views.fetch_employees, name='fetch_employees'),
    path('logout/', LogoutView.as_view(), name='logout'),
    

]