from django.contrib import admin
from .models import Position, LeaveRequest

# Register your models here.


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'salary_grade')
    list_filter = ('company',)
    search_fields = ('title',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status')
    list_filter = ('company', 'leave_type', 'status')
    date_hierarchy = 'start_date'
    actions = ['approve_requests', 'deny_requests']

    def approve_requests(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f"{queryset.count()} leave(s) approved.")
    approve_requests.short_description = "Approve selected leave requests"

    def deny_requests(self, request, queryset):
        queryset.update(status='denied')
        self.message_user(request, f"{queryset.count()} leave(s) denied.")
    deny_requests.short_description = "Deny selected leave requests"
