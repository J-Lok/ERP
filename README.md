# Erpis ERP — Multi-Tenant Enterprise Platform
### Modern Cloud Operations, Double-Entry Accounting, HRMS & Omnichannel Commerce
**Django 6.0 · Python 3.12 · Bootstrap 5 · PostgreSQL / SQLite · Docker Ready**

---

## Overview

**Erpis** is a comprehensive, production-ready, multi-tenant Enterprise Resource Planning (ERP) platform built on Django 6.0. It provides an all-in-one suite of business applications designed for fast-growing companies and SMEs, with native bilingual support (English & French), regional multi-currency (including FCFA), and direct-to-consumer/B2B commerce integration.

The platform consists of **11 core Django applications**, **42 database models**, **192 server-rendered responsive templates**, and an automated commerce-to-finance ledger pipeline.

---

## System Architecture & Core Modules

```
                                 ┌───────────────────────────────────┐
                                 │           ERPIS PLATFORM          │
                                 └─────────────────┬─────────────────┘
                                                   │
         ┌───────────────────┬─────────────────────┼─────────────────────┬───────────────────┐
         │                   │                     │                     │                   │
         ▼                   ▼                     ▼                     ▼                   ▼
┌─────────────────┐ ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ ┌─────────────────┐
│ Multi-Tenancy   │ │ Financial Core  │   │ People & Talent │   │ Commerce & CRM  │ │ Governance & Ops│
│ & Security      │ │ Double-Entry    │   │ Full Payroll    │   │ Zero-Sync Store │ │ Meetings, Notes │
│ Token Invites   │ │ General Ledger  │   │ Leave Requests  │   │ B2B Pipeline    │ │ Action Items    │
│ Domain Scoping  │ │ Bank Reconcile  │   │ Reviews & Skills│   │ Stock Locking   │ │ Tasks & Projects│
│ Custom SMTP     │ │ Invoicing & Tax │   │ Salary Grades   │   │ RMA & Reviews   │ │ In-App Alerts   │
└─────────────────┘ └─────────────────┘   └─────────────────┘   └─────────────────┘ └─────────────────┘
```

### Applications Reference

| App | Purpose | Key Models & Capabilities |
| :--- | :--- | :--- |
| **`accounts`** | Multi-tenancy, authentication & tenant config | `Company`, `User`, `Invitation`, `CompanyEmailSettings`. Enforces UUID company isolation, custom email-as-username login, 7-day tokenized user invitations, per-company custom SMTP, and mobile money/WhatsApp contact configuration. |
| **`finance`** | Full double-entry accounting & treasury | `Account` (hierarchical chart of accounts), `Journal`, `JournalEntry`, `JournalEntryLine` (balanced debit/credit), `ClientInvoice`, `SupplierInvoice`, `InvoiceLine` with PDF printing, `BankAccount`, `BankStatement`, `BankTransaction`, `Reconciliation`, `FinancialReport`, and `MarketplaceFinanceSettings`. |
| **`hr`** | Human resources, payroll & talent development | `Position` (with salary grades), `LeaveRequest` (6 leave types with approve/deny workflows and employee status sync), `SalaryComponent`, `PayrollPeriod`, `PayrollEntry`, `Payslip` (with auto-generation, locking, and email delivery), `PerformanceGoal`, `PerformanceReview`, `TrainingCourse`, `TrainingSession`, `EmployeeTraining`, `Skill`, and `EmployeeSkill`. |
| **`inventory`** | Warehouse & stock management | `StockCategory`, `Stock`, `StockTransaction`. Real-time stock valuation at cost and selling prices, low-stock reorder thresholds, automated Excel import & export with embedded product photo thumbnails, and atomic stock quantity adjustments using pessimistic database row-locking (`select_for_update()`). |
| **`marketplace`** | Integrated omnichannel storefront & fulfillment | `Client` (platform customer registration), `Cart`, `CartItem`, `Order`, `OrderItem`, `Wishlist`, `ProductReview`, `ReturnRequest` (RMA workflow), and `CompanyPaymentSettings` (MTN MoMo, Orange Money, Wave, WhatsApp ordering). Automatically posts sales entries to the finance ledger and issues reversal entries on returns. Complete Admin Order Fulfillment dashboard (Confirm, Ship, Deliver, Cancel, Invoice PDF). |
| **`crm`** | Customer relationships & deal flow | `Contact` (synced with marketplace clients), `Note` (calls, emails, meetings), and `Opportunity` visual sales pipeline (Prospect → Qualified → Proposal → Won/Lost) with deal values, follow-up dates, and direct invoice conversion. |
| **`meetings`** | Executive governance & team alignment | `Meeting`, `MeetingNote` (agenda, summaries, decisions made, risks identified, next steps, document uploads), `ActionItem` (assigned owners, deadlines, priority, completion tracking), and `MeetingAttachment`. |
| **`projects`** | Project management & task delegation | `Project` (budgeting, status, dates, managers), `SousTache` (subtasks with status transitions, assignees, dates), and `CommentaireTache`. Project completion percentage is automatically aggregated via database queries on subtask status changes. |
| **`employees`** | Staff directory & organizational structure | `Employee`, `Department`. Automatic profile creation upon User registration, employee role-to-permission mapping, and `terminate()` / `reactivate()` methods syncing linked user accounts. |
| **`notifications`** | In-app alert center & user preferences | `Notification` (read, unread, archive workflows, AJAX live counter) and `NotificationPreference` (granular per-user toggles across leave, payroll, reviews, meetings, and system alerts). |
| **`core`** | Dashboards & multi-tenant platform administration | Role-aware company dashboard (`show_employee_stats`, `show_finance_stats`, `show_hr_stats`), recent activity feeds, online user tracking, and superuser-only global platform dashboard (`platform_dashboard`). |

---

## Role-Based Access Control (RBAC)

All access control is declared in [`accounts/permissions.py`](file:///c:/Users/karlh/Desktop/ERP/ERP/management_system/accounts/permissions.py) using the `@role_required` and `@company_admin_required` decorators.

| Role | Access Level |
| :--- | :--- |
| **`admin`** | Full access to all company data, user invitations, email settings, and marketplace administration. |
| **`manager`** | Full operational access across projects, departments, employees, inventory, CRM, and meetings. |
| **`hr_manager`** | Full HRMS access: employee profiles, positions, leave approvals, payroll periods, and performance reviews. |
| **`accountant`** | Read and write access to chart of accounts, journal entries, client/supplier invoices, bank reconciliation, and financial reports. |
| **`stock_manager`** | Stock creation, adjustments, movements, categories, and marketplace catalog management. |
| **`secretary`** | CRM contacts, lead follow-ups, meeting scheduling, minutes recording, and self-service leave requests. |
| **`employee`** | Self-service portal: submit leave requests, track assigned projects/tasks, review performance goals, view payslips, and browse marketplace. |

---

## Getting Started

### Prerequisites
* **Python 3.12+**
* **Git**
* **PostgreSQL** (recommended for production) or **SQLite** (default for local development)

### Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/J-Lok/ERP.git
   cd ERP
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv env
   # Windows:
   .\env\Scripts\activate
   # Linux/macOS:
   source env/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Copy the example environment file:
   ```bash
   cp env.example management_system/.env
   ```
   *(For local SQLite development, leave `DATABASE_URL` empty or commented out).*

5. **Apply database migrations**:
   ```bash
   cd management_system
   python manage.py migrate
   ```

6. **Create a superuser**:
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server**:
   ```bash
   python manage.py runserver
   ```
   The platform is now available at `http://127.0.0.1:8000`.

---

## Running Automated Tests

The test suite covers all 11 applications with multi-tenant isolation, atomic stock adjustments, payroll math, role permissions, and governance:

```bash
cd management_system
python manage.py test accounts.tests core.tests crm.tests employees.tests finance.tests hr.tests inventory.tests marketplace.tests meetings.tests notifications.tests projects.tests
```

---

## Deployment

### Docker
```bash
docker build -t erp .
docker run -p 8000:8000 -e DATABASE_URL=postgresql://user:pass@host:5432/dbname erp
```

### Cloud Platforms (Render, Railway, Heroku) & VPS
The project includes production-ready configuration files:
* **`render.yaml`**, **`Procfile`**, and **`build.sh`** for cloud deployments (Render, Railway, Heroku).
* **`docker-compose.yml`** and **`docker-compose.prod.yml`** for multi-container development and production.
* **`deploy/vps-deploy.sh`** for self-hosted Ubuntu/Debian VPS deployments with Nginx and SSL.
* **Gunicorn** serves the WSGI application (`management_system.wsgi:application`).
* **WhiteNoise** serves compressed and version-hashed static files.
* **Cloudinary** handles persistent user-uploaded media (product images, documents, attachments).
* **SMTP / Resend** handles transactional emails and user invitations.

---

## Localization & Currencies

* **Languages**: English (`en`) and French (`fr`) fully translated in `management_system/locale/`. Users can switch their preferred interface language directly from their profile.
* **Currencies**: Built with native support for **FCFA**, EUR, and USD, alongside localized mobile payment options (Wave, Orange Money, MTN MoMo).

---

## Contributing

1. Fork the repository and create your feature branch (`git checkout -b feature/my-feature`).
2. Implement your changes following standard Django conventions and type annotations.
3. Verify system checks and run the test suite:
   ```bash
   python manage.py check
   python manage.py test
   ```
4. Commit your changes with clear, descriptive commit messages.
5. Open a Pull Request against the `main` branch.
