from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import role_required

from .models import Contact, Opportunity
from .forms import ContactForm, OpportunityForm


@role_required(['admin', 'manager', 'secretary'])
def index(request):
    return render(request, 'crm/index.html')


@role_required(['admin', 'manager', 'secretary'])
def contact_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    contacts = Contact.objects.filter(company=company).order_by('name')
    paginator = Paginator(contacts, 25)
    page = request.GET.get('page')
    try:
        contacts_page = paginator.page(page)
    except PageNotAnInteger:
        contacts_page = paginator.page(1)
    except EmptyPage:
        contacts_page = paginator.page(paginator.num_pages)
    return render(request, 'crm/contact_list.html', {'contacts': contacts_page})


@role_required(['admin', 'manager', 'secretary'])
def contact_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.company = company
            contact.save()
            messages.success(request, 'Contact saved.')
            return redirect('crm:contact_list')
    else:
        form = ContactForm()
    return render(request, 'crm/contact_form.html', {'form': form, 'title': 'New Contact'})


@role_required(['admin', 'manager', 'secretary'])
def opportunity_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    opps = Opportunity.objects.filter(company=company).select_related('contact').order_by('-created_at')
    paginator = Paginator(opps, 25)
    page = request.GET.get('page')
    try:
        opportunities_page = paginator.page(page)
    except PageNotAnInteger:
        opportunities_page = paginator.page(1)
    except EmptyPage:
        opportunities_page = paginator.page(paginator.num_pages)
    return render(request, 'crm/opportunity_list.html', {'opportunities': opportunities_page})


@role_required(['admin', 'manager', 'secretary'])
def opportunity_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = OpportunityForm(request.POST, company=company)
        if form.is_valid():
            opp = form.save(commit=False)
            opp.company = company
            opp.save()
            messages.success(request, 'Opportunity created.')
            return redirect('crm:opportunity_list')
    else:
        form = OpportunityForm(company=company)
    return render(request, 'crm/opportunity_form.html', {'form': form, 'title': 'New Opportunity'})


@role_required(['admin', 'manager', 'secretary'])
def contact_edit(request, pk):
    company = request.user.company
    contact = get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contact updated.')
            return redirect('crm:contact_list')
    else:
        form = ContactForm(instance=contact)
    return render(request, 'crm/contact_form.html', {'form': form, 'title': 'Edit Contact'})


@role_required(['admin', 'manager', 'secretary'])
def opportunity_edit(request, pk):
    company = request.user.company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    if request.method == 'POST':
        form = OpportunityForm(request.POST, instance=opp, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Opportunity updated.')
            return redirect('crm:opportunity_list')
    else:
        form = OpportunityForm(instance=opp, company=company)
    return render(request, 'crm/opportunity_form.html', {'form': form, 'title': 'Edit Opportunity'})


@role_required(['admin', 'manager', 'secretary'])
def contact_delete(request, pk):
    company = request.user.company
    contact = get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, f'Contact {contact.name} deleted.')
        contact.delete()
        return redirect('crm:contact_list')
    return render(request, 'crm/contact_confirm_delete.html', {'contact': contact})


@role_required(['admin', 'manager', 'secretary'])
def opportunity_delete(request, pk):
    company = request.user.company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, f'Opportunity {opp.title} deleted.')
        opp.delete()
        return redirect('crm:opportunity_list')
    return render(request, 'crm/opportunity_confirm_delete.html', {'opportunity': opp})
