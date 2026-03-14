"""
finance/views.py — upgraded

Views:
  - index         : dashboard with stats, recent transactions, account balances
  - account_list  : searchable paginated list
  - account_detail: per-account transaction history + running balance
  - account_create / account_edit / account_delete
  - transaction_list  : filterable by account, type, date range + search
  - transaction_create / transaction_edit / transaction_delete
"""

from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required

from .forms import AccountForm, TransactionForm
from .models import Account, Transaction

FINANCE_ROLES = ('admin', 'accountant', 'manager')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@role_required(*FINANCE_ROLES)
def index(request):
    company = request.user.company
    today = date.today()
    month_start = today.replace(day=1)

    accounts = Account.objects.filter(company=company)
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or 0

    txns = Transaction.objects.filter(company=company)
    total_credits = txns.filter(transaction_type='credit').aggregate(s=Sum('amount'))['s'] or 0
    total_debits  = txns.filter(transaction_type='debit').aggregate(s=Sum('amount'))['s'] or 0

    # This month
    month_txns = txns.filter(date__gte=month_start)
    month_credits = month_txns.filter(transaction_type='credit').aggregate(s=Sum('amount'))['s'] or 0
    month_debits  = month_txns.filter(transaction_type='debit').aggregate(s=Sum('amount'))['s'] or 0

    recent_txns = (
        txns
        .select_related('account', 'entered_by')
        .order_by('-date', '-created_at')[:10]
    )

    top_accounts = accounts.order_by('-balance')[:5]

    context = {
        'total_balance': total_balance,
        'total_credits': total_credits,
        'total_debits': total_debits,
        'month_credits': month_credits,
        'month_debits': month_debits,
        'net_month': month_credits - month_debits,
        'account_count': accounts.count(),
        'recent_txns': recent_txns,
        'top_accounts': top_accounts,
        'today': today,
    }
    return render(request, 'finance/index.html', context)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@role_required(*FINANCE_ROLES)
def account_list(request):
    company = request.user.company
    qs = Account.objects.filter(company=company)

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(name__icontains=query)

    paginator = Paginator(qs.order_by('name'), 25)
    page = request.GET.get('page')
    try:
        accounts_page = paginator.page(page)
    except PageNotAnInteger:
        accounts_page = paginator.page(1)
    except EmptyPage:
        accounts_page = paginator.page(paginator.num_pages)

    total_balance = qs.aggregate(total=Sum('balance'))['total'] or 0

    return render(request, 'finance/account_list.html', {
        'accounts': accounts_page,
        'query': query,
        'total_balance': total_balance,
    })


@role_required(*FINANCE_ROLES)
def account_detail(request, pk):
    company = request.user.company
    acct = get_object_or_404(Account, pk=pk, company=company)

    txns = (
        Transaction.objects
        .filter(account=acct)
        .select_related('entered_by')
        .order_by('-date', '-created_at')
    )

    # Filters
    type_filter = request.GET.get('type', '').strip()
    if type_filter:
        txns = txns.filter(transaction_type=type_filter)

    date_from = request.GET.get('date_from', '').strip()
    date_to   = request.GET.get('date_to', '').strip()
    if date_from:
        txns = txns.filter(date__gte=date_from)
    if date_to:
        txns = txns.filter(date__lte=date_to)

    paginator = Paginator(txns, 25)
    page = request.GET.get('page')
    try:
        txns_page = paginator.page(page)
    except PageNotAnInteger:
        txns_page = paginator.page(1)
    except EmptyPage:
        txns_page = paginator.page(paginator.num_pages)

    credits = txns.filter(transaction_type='credit').aggregate(s=Sum('amount'))['s'] or 0
    debits  = txns.filter(transaction_type='debit').aggregate(s=Sum('amount'))['s'] or 0

    return render(request, 'finance/account_detail.html', {
        'account': acct,
        'transactions': txns_page,
        'credits': credits,
        'debits': debits,
        'type_filter': type_filter,
        'date_from': date_from,
        'date_to': date_to,
    })


@role_required(*FINANCE_ROLES)
def account_create(request):
    company = request.user.company
    if request.method == 'POST':
        form = AccountForm(request.POST, company=company)
        if form.is_valid():
            acct = form.save(commit=False)
            acct.company = company
            acct.save()
            messages.success(request, f'Account "{acct.name}" created.')
            return redirect('finance:account_list')
    else:
        form = AccountForm(company=company)
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'New Account'})


@role_required(*FINANCE_ROLES)
def account_edit(request, pk):
    company = request.user.company
    acct = get_object_or_404(Account, pk=pk, company=company)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=acct, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Account "{acct.name}" updated.')
            return redirect('finance:account_list')
    else:
        form = AccountForm(instance=acct, company=company)
    return render(request, 'finance/account_form.html', {'form': form, 'title': 'Edit Account'})


@role_required(*FINANCE_ROLES)
def account_delete(request, pk):
    company = request.user.company
    acct = get_object_or_404(Account, pk=pk, company=company)
    if request.method == 'POST':
        name = acct.name
        acct.delete()
        messages.success(request, f'Account "{name}" deleted.')
        return redirect('finance:account_list')
    return render(request, 'finance/account_confirm_delete.html', {'account': acct})


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@role_required(*FINANCE_ROLES)
def transaction_list(request):
    company = request.user.company
    qs = (
        Transaction.objects
        .filter(company=company)
        .select_related('account', 'entered_by')
        .order_by('-date', '-created_at')
    )

    # Filters
    account_filter = request.GET.get('account', '').strip()
    if account_filter:
        qs = qs.filter(account_id=account_filter)

    type_filter = request.GET.get('type', '').strip()
    if type_filter:
        qs = qs.filter(transaction_type=type_filter)

    date_from = request.GET.get('date_from', '').strip()
    date_to   = request.GET.get('date_to', '').strip()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(description__icontains=query) |
            Q(account__name__icontains=query)
        )

    # Totals on filtered set
    credits = qs.filter(transaction_type='credit').aggregate(s=Sum('amount'))['s'] or 0
    debits  = qs.filter(transaction_type='debit').aggregate(s=Sum('amount'))['s'] or 0

    paginator = Paginator(qs, 25)
    page = request.GET.get('page')
    try:
        txns_page = paginator.page(page)
    except PageNotAnInteger:
        txns_page = paginator.page(1)
    except EmptyPage:
        txns_page = paginator.page(paginator.num_pages)

    accounts = Account.objects.filter(company=company).order_by('name')

    return render(request, 'finance/transaction_list.html', {
        'transactions': txns_page,
        'accounts': accounts,
        'account_filter': account_filter,
        'type_filter': type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'query': query,
        'credits': credits,
        'debits': debits,
        'net': credits - debits,
    })


@role_required(*FINANCE_ROLES)
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
    return render(request, 'finance/transaction_form.html', {
        'form': form, 'title': 'New Transaction'
    })


@role_required(*FINANCE_ROLES)
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
    return render(request, 'finance/transaction_form.html', {
        'form': form, 'title': 'Edit Transaction'
    })


@role_required(*FINANCE_ROLES)
def transaction_delete(request, pk):
    company = request.user.company
    txn = get_object_or_404(Transaction, pk=pk, company=company)
    if request.method == 'POST':
        txn.delete()
        messages.success(request, 'Transaction deleted.')
        return redirect('finance:transaction_list')
    return render(request, 'finance/transaction_confirm_delete.html', {'transaction': txn})