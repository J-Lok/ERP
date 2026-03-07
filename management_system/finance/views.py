from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import role_required

from .models import Account, Transaction
from .forms import AccountForm, TransactionForm


# finance dashboard
@role_required(['admin', 'accountant', 'manager'])
def index(request):
    return render(request, 'finance/index.html')


@role_required(['admin', 'accountant', 'manager'])
def account_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    accounts = Account.objects.filter(company=company).order_by('name')
    paginator = Paginator(accounts, 25)
    page = request.GET.get('page')
    try:
        accounts_page = paginator.page(page)
    except PageNotAnInteger:
        accounts_page = paginator.page(1)
    except EmptyPage:
        accounts_page = paginator.page(paginator.num_pages)
    return render(request, 'finance/account_list.html', {'accounts': accounts_page})


@role_required(['admin', 'accountant', 'manager'])
def account_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            acct = form.save(commit=False)
            acct.company = company
            acct.save()
            messages.success(request, 'Account created successfully.')
            return redirect('finance:account_list')
    else:
        form = AccountForm()
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'New Account'})


@role_required(['admin', 'accountant', 'manager'])
def transaction_list(request):
    company = request.user.company
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    txns = Transaction.objects.filter(company=company).select_related('account').order_by('-date')
    paginator = Paginator(txns, 25)
    page = request.GET.get('page')
    try:
        transactions_page = paginator.page(page)
    except PageNotAnInteger:
        transactions_page = paginator.page(1)
    except EmptyPage:
        transactions_page = paginator.page(paginator.num_pages)
    return render(request, 'finance/transaction_list.html', {'transactions': transactions_page})


@role_required(['admin', 'accountant', 'manager'])
def transaction_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = TransactionForm(request.POST, company=company)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.company = company
            txn.entered_by = request.user
            txn.save()
            messages.success(request, 'Transaction recorded.')
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(company=company)
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': 'New Transaction'})


@role_required(['admin', 'accountant', 'manager'])
def account_edit(request, pk):
    company = request.user.company
    acct = get_object_or_404(Account, pk=pk, company=company)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=acct)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account updated successfully.')
            return redirect('finance:account_list')
    else:
        form = AccountForm(instance=acct)
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'Edit Account'})


@role_required(['admin', 'accountant', 'manager'])
def transaction_edit(request, pk):
    company = request.user.company
    txn = get_object_or_404(Transaction, pk=pk, company=company)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=txn, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated.')
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(instance=txn, company=company)
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': 'Edit Transaction'})


@role_required(['admin', 'accountant', 'manager'])
def account_delete(request, pk):
    company = request.user.company
    acct = get_object_or_404(Account, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, f'Account {acct.name} deleted.')
        acct.delete()
        return redirect('finance:account_list')
    return render(request, 'finance/account_confirm_delete.html', {'account': acct})


@role_required(['admin', 'accountant', 'manager'])
def transaction_delete(request, pk):
    company = request.user.company
    txn = get_object_or_404(Transaction, pk=pk, company=company)
    if request.method == 'POST':
        messages.success(request, 'Transaction deleted.')
        txn.delete()
        return redirect('finance:transaction_list')
    return render(request, 'finance/transaction_confirm_delete.html', {'transaction': txn})
