"""Business document archetypes, independent of the file format.

Builders describe meaning (payroll, incident report, Kubernetes manifest) and
use one coherent organisation.  The renderer decides whether that meaning lands
as CSV, XLSX, PDF, DOCX, YAML, a log or a screenshot.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from ..entities import EntityPool
from ..models import Entity
from .docmodel import Doc, DocBuilder, cell
from .localization import format_currency, format_date, label as localize_label
from .org import OrgProfile, Person
from .scenario import ScenarioPlan, safe_negative as _safe_negative, validate_log_order

RENDERERS_ALL_TEXT = ("txt", "md", "docx", "pdf")
TABLE_RENDERERS = ("csv", "xlsx", "docx", "pdf", "txt")
REPORT_RENDERERS = ("docx", "pdf", "md", "txt")
CONFIG_RENDERERS = ("env", "yaml", "yml", "json", "ini", "conf", "toml", "txt", "md", "png", "jpg")
LOG_RENDERERS = ("log", "txt", "md", "json", "png", "jpg")
CODE_RENDERERS = ("py", "js", "ts", "java", "go", "txt", "md", "png", "jpg")
IMAGE_RENDERERS = ("png", "jpg", "jpeg")
SLIDE_RENDERERS = ("pptx", "pdf")


@dataclass
class BuildContext:
    rng: random.Random
    language: str
    org: OrgProfile
    pool: EntityPool
    domains: Sequence[str]
    negative: bool = False
    ambiguous: bool = False
    density: int = 2
    doc_language: str = "en"
    image_style: str = "scan"
    ocr_difficulty: int = 2
    scenario: Optional[ScenarioPlan] = None
    variant: int = 1
    attachment_id: str = "ATT-001"
    latin_only: Optional[bool] = None

    def wants(self, domain: str) -> bool:
        return domain in self.domains

    def shared(self, domain: str, entity_type: Optional[str] = None,
               key: Optional[str] = None) -> Entity:
        if self.scenario is None:
            raise RuntimeError("BuildContext.shared requires a ScenarioPlan")
        return self._latin(self.scenario.shared(domain, entity_type, key))

    def label(self, value: str) -> str:
        return localize_label(value, self.doc_language)

    def money(self, amount: float) -> str:
        return format_currency(amount, self.doc_language,
                               self.scenario.currency_mode if self.scenario else "thb")

    def date(self, value) -> str:
        return format_date(value, self.doc_language,
                           self.scenario.thai_date_mode if self.scenario else "be")

    def check(self, name: str, status, details: dict,
              evaluated_items: Optional[int] = None) -> None:
        if self.scenario is not None:
            self.scenario.record_check(name, status, details, self.attachment_id,
                                       evaluated_items)

    def observation(self, key: str, value) -> None:
        if self.scenario is not None:
            self.scenario.observe(key, value, self.attachment_id, self.doc_language)

    def csv_delimiter(self) -> str:
        return self.rng.choices([",", ";", "\t"], weights=[0.72, 0.20, 0.08], k=1)[0]

    def entity(self, domain: str, types: Optional[Sequence[str]] = None) -> Entity:
        if self.negative and not self.ambiguous:
            return self._latin(_safe_negative(self.rng, self._type_for(domain, types)))
        if self.ambiguous and self.rng.random() < 0.3:
            return self._latin(_safe_negative(self.rng, self._type_for(domain, types)))
        return self._latin(self.pool.draw(domain, self._pick_type(domain, types)))

    def _latin(self, entity: Entity) -> Entity:
        if self.scenario is None:
            return entity
        latin_only = (self.latin_only if self.latin_only is not None
                      else self.scenario.latin_only)
        return self.scenario.latinize(entity) if latin_only else entity

    def _type_for(self, domain: str, types: Optional[Sequence[str]]) -> str:
        if types:
            return types[0]
        from ..entities import entity_types
        return entity_types(domain)[0]

    def _pick_type(self, domain: str, types: Optional[Sequence[str]]) -> Optional[str]:
        if types:
            return types[self.rng.randrange(len(types))]
        return None

    def maybe(self, value: Optional[Entity], probability: float = 0.6) -> Optional[Entity]:
        if value is None:
            return None
        return value if self.rng.random() < probability else None

    def _document_identity(self, entity: Entity, entity_type: str) -> Entity:
        """A realistic identity that is not the oracle's sensitive target."""
        return Entity("lookalike", entity_type, entity.value, detection_expected=False,
                      note="synthetic organisation identity, not an annotated target entity")

    def person_name(self, person: Person, index: int = 0) -> Entity | str:
        if self.negative or not self.wants("pii"):
            return self._document_identity(self._latin(person.name), "document_person_name")
        return self._latin(person.name)

    def person_email(self, person: Person, index: int = 0) -> Entity | str:
        if self.negative or not self.wants("pii"):
            return self._document_identity(self._latin(person.email), "document_email")
        return self._latin(person.email)

    def person_phone(self, person: Person, index: int = 0) -> Entity | str:
        if self.negative or not self.wants("pii"):
            return self._document_identity(self._latin(person.phone), "document_phone")
        return self._latin(person.phone)

    def person_field(self, person: Person, attr: str, domain: str, types: Sequence[str]) -> Entity | str:
        if not self.wants(domain):
            return "Not provided"
        if self.negative and not self.ambiguous:
            return _safe_negative(self.rng, types[0]).value
        value = getattr(person, attr)
        if value is None:
            value = self.pool.draw(domain, self.rng.choice(types))
            setattr(person, attr, value)
        return self._latin(value)


@dataclass(frozen=True)
class Archetype:
    id: str
    label: str
    category: str
    domains: tuple
    renderers: tuple
    difficulty: int
    builder: Callable[[BuildContext], Doc]
    rationale: str
    tags: tuple = ()


# --------------------------------------------------------------------------
# People and operations tables
# --------------------------------------------------------------------------


def _people_rows(ctx: BuildContext, people: Sequence[Person], fields: Sequence[str]) -> List[List[Any]]:
    rows = []
    limit = min(len(people), max(3, ctx.rng.randint(3, max(3, len(people)))))
    for index, person in enumerate(people[:limit]):
        row: List[Any] = []
        for field_name in fields:
            if field_name == "name":
                row.append(ctx.person_name(person, index))
            elif field_name == "email":
                row.append(ctx.person_email(person, index))
            elif field_name == "phone":
                row.append(ctx.person_phone(person, index))
            elif field_name == "address":
                row.append(ctx.person_field(person, "address", "pii", ["thai_address"]))
            elif field_name == "national_id":
                row.append(ctx.person_field(person, "national_id", "pii", ["thai_national_id"]))
            elif field_name == "dob":
                row.append(ctx.person_field(person, "dob", "pii", ["date_of_birth"]))
            elif field_name == "bank":
                row.append(ctx.person_field(person, "bank", "payment", ["bank_account_number"]))
            elif field_name == "card":
                row.append(ctx.entity("payment", ["payment_card_number"]))
            elif field_name == "card_expiry":
                row.append(ctx.entity("payment", ["card_expiry_date"]))
            elif field_name == "transaction":
                row.append(ctx.shared("payment", "payment_transaction_reference", f"txn_{index}"))
            elif field_name == "amount":
                row.append(f"{ctx.rng.randrange(1200, 98000):,}.00")
            elif field_name == "host":
                row.append(ctx.shared("infrastructure", "internal_hostname", f"host_{index % 4}"))
            elif field_name == "ip":
                row.append(ctx.shared("infrastructure", "internal_ipv4", f"ip_{index % 4}"))
            elif field_name == "db":
                row.append(ctx.shared("infrastructure", "database_endpoint", "db_endpoint"))
            elif field_name == "url":
                row.append(ctx.shared("infrastructure", "internal_url", "url"))
            elif field_name == "secret":
                row.append(ctx.shared("secrets", "api_key", "api_key"))
            else:
                row.append(field_name)
        rows.append(row)
    return rows


def _employee_list(ctx: BuildContext) -> Doc:
    builder = DocBuilder("employee_list", "Employee list", "employee_list.xlsx", ctx.doc_language)
    builder.heading("Employee directory")
    builder.para("Export from the people system. Internal use only.")
    fields = ["name", "email", "phone"]
    headers = ["name", "email", "phone"]
    if ctx.wants("pii"):
        if ctx.rng.random() < 0.7:
            fields.append("national_id"); headers.append("national_id")
        if ctx.rng.random() < 0.6:
            fields.append("address"); headers.append("address")
    if ctx.wants("payment"):
        fields.append("bank"); headers.append("bank_account")
    builder.table(headers, _people_rows(ctx, ctx.org.employees, fields), title="Employees")
    if ctx.wants("infrastructure"):
        rows = [[ctx.shared("infrastructure", "internal_hostname", f"host_{index}"),
                 ctx.shared("infrastructure", "internal_ipv4", f"ip_{index}"),
                 ctx.person_email(ctx.org.employees[index], index)] for index in range(4)]
        builder.table(["hostname", "private_ip", "owner_email"], rows, title="Asset assignment")
    builder.note("Prepared for internal review.")
    return builder.build(header=cell(f"{ctx.org.name} - People Operations"),
                         footer=cell("HR - internal use only"),
                         hidden_sheets=["Asset assignment"] if ctx.wants("infrastructure") else [])


def _payroll(ctx: BuildContext) -> Doc:
    builder = DocBuilder("payroll", "Payroll register", "payroll_2026-03.xlsx", ctx.doc_language)
    builder.heading("Payroll register - March 2026")
    fields = ["name", "email"]
    headers = ["employee", "email"]
    if ctx.wants("payment"):
        fields.append("bank"); headers.append("bank_account")
    fields += ["amount", "amount", "amount"]
    headers += ["gross", "tax", "net"]
    rows = _people_rows(ctx, ctx.org.employees, fields)
    total_gross = 0
    total_tax = 0
    arithmetic_ok = True
    for index, row in enumerate(rows):
        gross = ctx.rng.randrange(35000, 110000)
        tax = int(gross * 0.05)
        net = gross - tax
        offset = len(row) - 3
        row[offset] = f"{gross:,}.00"
        row[offset + 1] = f"{tax:,}.00"
        row[offset + 2] = f"{net:,}.00"
        arithmetic_ok = arithmetic_ok and (gross - tax == net)
        total_gross += gross
        total_tax += tax
    builder.table(headers, rows, title="Payroll")
    ctx.check("payroll_arithmetic", arithmetic_ok, {
        "rows": len(rows), "gross_total": total_gross, "tax_total": total_tax,
        "net_total": total_gross - total_tax,
    })
    if ctx.wants("secrets"):
        builder.para("Bank transfer integration credential: ",
                     ctx.shared("secrets", "api_key", "payroll_api_key"))
    return builder.build(header=cell(f"{ctx.org.name} - Finance"),
                         footer=cell("Payroll - internal use only"))


def _customer_export(ctx: BuildContext) -> Doc:
    builder = DocBuilder("customer_export", "Customer export", "customer_export.csv", ctx.doc_language)
    builder.heading("Customer export")
    fields = ["name", "email", "phone"]
    headers = ["customer_name", "email", "phone"]
    if ctx.wants("pii"):
        fields += ["address"]; headers += ["address"]
    if ctx.wants("payment"):
        fields += ["card", "card_expiry"]; headers += ["card_on_file", "card_expiry"]
    rows = _people_rows(ctx, ctx.org.customers, fields)
    for index, row in enumerate(rows):
        row.insert(0, f"CUS-{1000 + index}")
    builder.table(["customer_id"] + headers, rows, title="Customers")
    builder.note("Exported for a customer-success review.")
    return builder.build(delimiter=ctx.csv_delimiter())


def _transaction_export(ctx: BuildContext) -> Doc:
    builder = DocBuilder("transaction_export", "Transaction export", "transactions_2026-03.csv", ctx.doc_language)
    builder.heading("Transaction export - March 2026")
    headers = ["date", "customer", "email", "amount", "status"]
    rows = []
    finance = ctx.scenario.finance(4) if ctx.scenario is not None else None
    if finance is not None:
        # The settlement of the invoice in this bundle: same reference, same
        # amount and same currency as the document it settles.
        customer = ctx.org.customers[0]
        row: List[Any] = [
            finance["payment_date"],
            ctx.person_name(customer, 0),
            ctx.person_email(customer, 0),
            f"{finance['total']:,}.00",
            "settled",
        ]
        if ctx.wants("payment"):
            row[0:0] = [finance["transaction_id"]]
            row.extend([ctx.shared("payment", "payment_card_number", "corp_card"),
                        ctx.entity("payment", ["payment_authorization_code"])])
        rows.append(row)
        ctx.observation("finance.total", finance["total"])
        ctx.observation("finance.currency", finance["currency"])
        if ctx.wants("payment"):
            ctx.observation("finance.transaction_reference", finance["transaction_id"])
    for index in range(6):
        customer = ctx.org.customers[index % len(ctx.org.customers)]
        row = [
            f"2026-03-{10 + index:02d}",
            ctx.person_name(customer, index),
            ctx.person_email(customer, index),
            f"{ctx.rng.randrange(500, 24000):,}.00",
            ctx.rng.choice(["settled", "settled", "pending", "refunded"]),
        ]
        if ctx.wants("payment"):
            row[0:0] = [ctx.shared("payment", "payment_transaction_reference", f"txn_{index + 1}")]
            row.extend([ctx.shared("payment", "payment_card_number", "corp_card"),
                        ctx.entity("payment", ["payment_authorization_code"])])
        rows.append(row)
    if ctx.wants("payment"):
        headers = ["transaction_ref"] + headers + ["card", "auth_code"]
    if finance is not None:
        headers = headers + ["currency"]
        for position, row in enumerate(rows):
            row.append(finance["currency"] if position == 0 else
                       ("THB" if (ctx.scenario and ctx.scenario.currency_mode == "thb") else "XXX"))
    builder.table(headers, rows, title="Transactions")
    return builder.build(delimiter=ctx.csv_delimiter())


def _patient_list(ctx: BuildContext) -> Doc:
    builder = DocBuilder("patient_list", "Patient appointment list", "patient_list.xlsx", ctx.doc_language)
    builder.heading("Clinic appointment list")
    rows = []
    for index in range(6):
        person = ctx.org.customers[index % len(ctx.org.customers)]
        rows.append([
            ctx.entity("pii", ["patient_id"]),
            ctx.person_name(person, index),
            ctx.person_field(person, "dob", "pii", ["date_of_birth"]),
            ctx.person_phone(person, index),
            ctx.entity("pii", ["health_condition"]),
            f"2026-03-{12 + index:02d} 09:{30 + index:02d}",
        ])
    builder.table(["HN", "patient", "dob", "phone", "diagnosis", "appointment"], rows, title="Appointments")
    builder.note("Clinic appointment data for internal review.")
    return builder.build()


def _server_inventory(ctx: BuildContext) -> Doc:
    builder = DocBuilder("server_inventory", "Server inventory", "server_inventory.csv", ctx.doc_language)
    builder.heading("Server inventory")
    rows = []
    for index in range(len(ctx.org.hosts)):
        rows.append([
            ctx.shared("infrastructure", "internal_hostname", f"host_{index}")
            if ctx.wants("infrastructure") else "app-host",
            ctx.shared("infrastructure", "internal_ipv4", f"ip_{index}")
            if ctx.wants("infrastructure") else "192.0.2.10",
            ctx.rng.choice(["api", "worker", "database", "gateway"]),
            ctx.person_email(ctx.org.employees[index % len(ctx.org.employees)], index),
            ctx.rng.choice(["production", "staging"]),
        ])
    builder.table(["hostname", "private_ip", "role", "owner_email", "environment"], rows, title="Servers")
    return builder.build()


def _sales_pipeline(ctx: BuildContext) -> Doc:
    builder = DocBuilder("sales_pipeline", "Sales pipeline", "sales_pipeline.xlsx", ctx.doc_language)
    builder.heading("Sales pipeline - Q1 2026")
    rows = []
    for index, customer in enumerate(ctx.org.customers):
        rows.append([
            f"OPP-{2000 + index}",
            ctx.person_name(customer, index),
            ctx.person_email(customer, index),
            f"{ctx.rng.randrange(50000, 900000):,}",
            ctx.rng.choice(["qualified", "proposal", "negotiation", "won"]),
            ctx.entity("payment", ["payment_transaction_reference"]),
        ])
    builder.table(["opportunity", "customer", "contact_email", "amount", "stage", "reference"], rows, title="Pipeline")
    return builder.build()


def _access_records(ctx: BuildContext) -> Doc:
    builder = DocBuilder("access_records", "Access records", "access_records.csv", ctx.doc_language)
    builder.heading("Access log export")
    rows = []
    for index in range(8):
        person = ctx.org.employees[index % len(ctx.org.employees)]
        rows.append([
            f"2026-03-{10 + index:02d}T09:{10 + index:02d}:00Z",
            ctx.person_email(person, index),
            ctx.shared("infrastructure", "internal_ipv4", f"ip_{index % 4}")
            if ctx.wants("infrastructure") else "192.0.2.10",
            ctx.shared("infrastructure", "internal_hostname", f"host_{index % 4}")
            if ctx.wants("infrastructure") else "docs.example.org",
            ctx.rng.choice(["read", "write", "delete", "login"]),
        ])
    builder.table(["timestamp", "user", "source_ip", "resource", "action"], rows, title="Access events")
    log_result = validate_log_order([str(row[0]) for row in rows])
    ctx.check("log_timestamps_ordered", log_result["status"], {
        "entries": len(rows), "format": "iso",
        "first": log_result.get("first"), "last": log_result.get("last"),
        "reason": log_result.get("reason", ""),
    }, evaluated_items=log_result["evaluated_items"])
    return builder.build(delimiter=ctx.csv_delimiter())


def _vendor_list(ctx: BuildContext) -> Doc:
    builder = DocBuilder("vendor_list", "Vendor list", "vendor_list.xlsx", ctx.doc_language)
    builder.heading("Approved vendor list")
    rows = []
    for index, vendor in enumerate(ctx.org.vendors):
        person = ctx.org.vendor_contacts[index % len(ctx.org.vendor_contacts)]
        rows.append([
            vendor,
            ctx.person_name(person, index),
            ctx.person_email(person, index),
            ctx.person_phone(person, index),
            f"TAX-{ctx.rng.randint(100000, 999999)}",
        ])
    builder.table(["vendor", "contact", "email", "phone", "tax_reference"], rows, title="Vendors")
    return builder.build()


def _bank_statement(ctx: BuildContext) -> Doc:
    builder = DocBuilder("bank_statement", "Bank statement", "bank_statement_2026-03.pdf", ctx.doc_language)
    builder.heading("Bank statement")
    opening = ctx.rng.randrange(80000, 220000, 100)
    holder = ctx.person_name(ctx.org.employees[0])
    account = (ctx.shared("payment", "bank_account_number", "statement_account")
               if ctx.wants("payment") else "XXXX-0000")
    builder.para("Account holder: ", holder, " | Account: ", account)
    builder.para("Opening balance: ", ctx.money(opening), "  |  Date: ", ctx.date("2026-03-01"))
    rows = []
    balance = opening
    movements = []
    for index in range(ctx.rng.choice((7, 8, 9, 10))):
        direction = ctx.rng.choice(["credit", "credit", "debit"])
        amount = ctx.rng.randrange(150, 26000)
        balance += amount if direction == "credit" else -amount
        if balance < 0:
            direction = "credit"
            balance += amount * 2
        reference = (ctx.shared("payment", "payment_transaction_reference", f"stmt_txn_{index}")
                     if ctx.wants("payment") else f"REF-{1000 + index}")
        movements.append((amount, direction, balance))
        rows.append([
            ctx.date(f"2026-03-{10 + index:02d}"),
            ctx.rng.choice(["card settlement", "transfer", "refund", "service fee"]),
            reference,
            ctx.rng.choice(["credit", "debit"]),
            ctx.money(amount),
            ctx.money(balance),
        ])
    # Keep the type column aligned with the running-balance calculation.
    for row, (amount, direction, _balance) in zip(rows, movements):
        row[3] = direction
    builder.table(["date", "description", "reference", "type", "amount", "balance"],
                  rows, title="Transactions")
    expected = opening
    for amount, direction, balance in movements:
        expected += amount if direction == "credit" else -amount
        if expected != balance:
            break
    ctx.check("statement_running_balance", expected == balance and balance >= 0, {
        "opening_balance": opening, "closing_balance": balance,
        "movements": len(movements),
    })
    builder.para("Statement generated from the core banking export.")
    return builder.build(header=cell("Bank statement - internal"))


def _expense_report(ctx: BuildContext) -> Doc:
    builder = DocBuilder("expense_report", "Expense report", "expense_report_2026-03.xlsx", ctx.doc_language)
    builder.heading("Expense report")
    rows = []
    for index in range(6):
        person = ctx.org.employees[index % len(ctx.org.employees)]
        row = [
            f"2026-03-{10 + index:02d}",
            ctx.person_name(person, index),
            ctx.person_email(person, index),
            ctx.rng.choice(["travel", "software", "office", "training"]),
        ]
        if ctx.wants("payment"):
            row.append(ctx.entity("payment", ["payment_card_number"]))
        row.append(f"{ctx.rng.randrange(250, 18000):,}.00")
        rows.append(row)
    headers = ["date", "employee", "email", "category"] + (["card"] if ctx.wants("payment") else []) + ["amount"]
    builder.table(headers, rows, title="Expenses")
    return builder.build()


def _appointment_list(ctx: BuildContext) -> Doc:
    return _patient_list(ctx)


def _order_export(ctx: BuildContext) -> Doc:
    builder = DocBuilder("order_export", "Order export", "order_export.csv", ctx.doc_language)
    builder.heading("Order export")
    rows = []
    for index in range(8):
        customer = ctx.org.customers[index % len(ctx.org.customers)]
        rows.append([
            f"ORD-2026-{41000 + index}",
            ctx.person_name(customer, index),
            ctx.person_email(customer, index),
            ctx.person_field(customer, "address", "pii", ["thai_address"]),
            f"{ctx.rng.randrange(300, 12000):,}.00",
            ctx.rng.choice(["packed", "shipped", "delivered"]),
        ])
    builder.table(["order_id", "customer", "email", "address", "total", "status"], rows, title="Orders")
    return builder.build()


# --------------------------------------------------------------------------
# Finance and report documents
# --------------------------------------------------------------------------


def _finance_document(ctx: BuildContext, kind: str) -> Doc:
    filename = f"{kind}_2026-03.pdf"
    label = kind.replace("_", " ").title()
    builder = DocBuilder(kind, label, filename, ctx.doc_language)
    builder.heading(label)
    customer = ctx.org.customers[0]
    item_count = ctx.rng.choice((3, 4, 4, 5, 6))
    if ctx.scenario is not None:
        finance = ctx.scenario.finance(item_count)
    else:  # prompt-level builders always carry a scenario in the generator
        finance = {
            "invoice_number": f"{kind[:3].upper()}-2026-1000", "currency": "THB",
            "items": [{"description": "Item", "quantity": 1, "unit_price": 1000,
                       "line_total": 1000}],
            "subtotal": 1000, "tax": 70, "total": 1070, "invoice_date": "2026-03-18",
            "due_date": "2026-04-17", "payment_date": "2026-03-18",
            "transaction_id": "TXN-2026-100000", "payment_schedule": "single_payment",
        }
    number = finance["invoice_number"] if kind == "invoice" else (
        ctx.scenario.invoice_number(kind) if ctx.scenario else finance["invoice_number"])
    builder.para(ctx.label("Reference"), ": ", number, "  |  ", ctx.label("Date"), ": ",
                 ctx.date(finance["invoice_date"]), "  |  ", ctx.label("Due"), ": ",
                 ctx.date(finance["due_date"]))
    builder.para(ctx.label("Bill to"), ": ", ctx.person_name(customer), " | ", ctx.person_email(customer))
    if ctx.wants("pii"):
        builder.para(ctx.label("Address"), ": ", ctx.person_field(customer, "address", "pii", ["thai_address"]))
    rows = [[item["description"], item["quantity"],
             f"{item['unit_price']:,}.00", f"{item['line_total']:,}.00"]
            for item in finance["items"]]
    builder.table(["description", "quantity", "unit_price", "line_total"], rows, title="Items")
    subtotal = sum(item["line_total"] for item in finance["items"])
    tax = int(round(subtotal * finance.get("tax_rate", 0.07)))
    total = subtotal + tax
    # A summary table keeps the totals inside tabular renderers too; an XLSX
    # invoice must actually contain the amount its transaction settles.
    builder.table(["label", "value"], [
        [ctx.label("Subtotal"), f"{subtotal:,}.00"],
        [ctx.label("VAT 7%"), f"{tax:,}.00"],
        [ctx.label("Total"), f"{total:,}.00"],
        [ctx.label("Currency"), finance["currency"]],
    ], title="Summary")
    builder.para(f"{ctx.label('Subtotal')}: {subtotal:,}.00   "
                 f"{ctx.label('VAT 7%')}: {tax:,}.00   "
                 f"{ctx.label('Total')}: {total:,}.00   {finance['currency']}")
    ctx.observation("finance.total", total)
    ctx.observation("finance.currency", finance["currency"])
    ctx.check("invoice_arithmetic", subtotal + tax == total, {
        "line_items": len(rows), "subtotal": subtotal, "tax": tax, "total": total,
    }, evaluated_items=len(rows))
    due_ok = finance["due_date"] > finance["invoice_date"]
    ctx.check("invoice_due_date", due_ok, {
        "issue_date": finance["invoice_date"], "due_date": finance["due_date"],
        "terms_days": ctx.scenario.payment_terms_days if ctx.scenario else 30,
    }, evaluated_items=1)
    if ctx.wants("payment"):
        builder.para(ctx.label("Transaction reference"), ": ", finance["transaction_id"])
        ctx.observation("finance.transaction_reference", finance["transaction_id"])
        builder.para(ctx.label("Card on file"), ": ",
                     ctx.shared("payment", "payment_card_number", "corp_card"),
                     "  ", ctx.label("Expiry"), ": ", ctx.entity("payment", ["card_expiry_date"]),
                     "  ", ctx.label("Authorization"), ": ",
                     ctx.entity("payment", ["payment_authorization_code"]))
    if ctx.wants("secrets"):
        builder.para(ctx.label("Payment gateway key"), ": ", ctx.shared("secrets", "api_key", "api_key"))
    if ctx.wants("infrastructure"):
        builder.para(ctx.label("Billing service endpoint"), ": ",
                     ctx.shared("infrastructure", "internal_url", "url"))
    builder.para("Invoice document.")
    return builder.build(header=cell(f"{ctx.org.name} - Finance"),
                         footer=cell("Finance - internal use only"))


def _contract(ctx: BuildContext, kind: str) -> Doc:
    title = {"employment_contract": "Employment contract", "nda": "Non-disclosure agreement",
             "supplier_agreement": "Supplier agreement", "customer_contract": "Customer contract"}.get(
        kind, "Contract")
    builder = DocBuilder(kind, title, f"{kind}.docx", ctx.doc_language)
    builder.heading(title)
    employee = ctx.org.employees[0]
    builder.para("Between ", ctx.org.name, " and ", ctx.person_name(employee), " (", ctx.person_email(employee), ").")
    if ctx.wants("pii"):
        builder.para("Address: ", ctx.person_field(employee, "address", "pii", ["thai_address"]),
                     "  National ID: ", ctx.person_field(employee, "national_id", "pii", ["thai_national_id"]))
    builder.heading("1. Scope")
    builder.para("This agreement covers services for ", ctx.rng.choice(ctx.org.projects),
                 " and is provided only as a test document.")
    builder.heading("2. Confidentiality")
    builder.para("The parties shall protect confidential information and may disclose it only to authorised staff.")
    if ctx.wants("secrets"):
        builder.para("Integration credential referenced in schedule A: ",
                     ctx.shared("secrets", "api_key", "api_key"))
    if ctx.wants("payment"):
        builder.para("Payment account: ", ctx.shared("payment", "bank_account_number", "contract_account"),
                     " Reference: ", ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    if ctx.wants("infrastructure"):
        builder.para("Internal service: ", ctx.shared("infrastructure", "internal_url", "url"))
    builder.heading("3. Signatures")
    builder.para("Signed for ", ctx.org.name, " by ", ctx.person_name(ctx.org.employees[1]), " on 2026-03-18.")
    return builder.build(header=cell("Confidential"))


def _cv(ctx: BuildContext) -> Doc:
    candidate = ctx.org.customers[2]
    builder = DocBuilder("cv", "Curriculum vitae", "candidate_cv.docx", ctx.doc_language)
    builder.heading("Curriculum vitae")
    builder.para(ctx.person_name(candidate))
    builder.para(ctx.person_email(candidate), " | ", ctx.person_phone(candidate))
    if ctx.wants("pii"):
        builder.para(ctx.person_field(candidate, "address", "pii", ["thai_address"]),
                     " | DOB: ", ctx.person_field(candidate, "dob", "pii", ["date_of_birth"]))
    builder.heading("Experience")
    builder.bullet("Senior analyst at a logistics company, 2021-2026.")
    builder.bullet("Built reporting pipelines and reviewed vendor contracts.")
    builder.heading("Skills")
    builder.para("SQL, Python, spreadsheet modelling, stakeholder communication.")
    return builder.build(header=cell("Candidate CV"))


def _incident_report(ctx: BuildContext) -> Doc:
    builder = DocBuilder("incident_report", "Incident report", "incident_report.docx", ctx.doc_language)
    reporter = ctx.org.employees[0]
    incident_id = ctx.scenario.incident_id if ctx.scenario else "INC-2026-0318"
    builder.heading("Incident report - API authentication failures")
    builder.para("Incident ID: ", incident_id, "  |  Reported by: ", ctx.person_name(reporter),
                 " (", ctx.person_email(reporter), ")")
    builder.para("Date: ", ctx.date("2026-03-18"), "  |  Request ID: ",
                 ctx.scenario.request_id(0) if ctx.scenario else "req-10231")
    builder.heading("Summary")
    builder.para("At 09:12 the API gateway returned 502 responses for requests to the order service. "
                 "The application could not connect to the database after the previous deployment.")
    if ctx.wants("infrastructure"):
        builder.para("Affected host: ", ctx.shared("infrastructure", "internal_hostname", "host_0"),
                     " (", ctx.shared("infrastructure", "internal_ipv4", "ip_0"), ")")
        builder.para("Database endpoint: ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint"),
                     "  Network: ", ctx.shared("infrastructure", "private_network", "network"))
        builder.para("Service URL: ", ctx.shared("infrastructure", "internal_url", "url"))
    if ctx.wants("secrets"):
        builder.para("The deployment log printed the following credential while retrying: ",
                     ctx.shared("secrets", "database_credential", "db_credential"))
        builder.para("Connection string in the failed job: ",
                     ctx.shared("secrets", "connection_string", "db_connection_string"))
    if ctx.wants("payment"):
        builder.para("Payment retry queue reference: ",
                     ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    if ctx.rng.random() < 0.5:
        builder.heading("Impact")
        builder.para("Checkout requests failed for approximately 29 minutes. "
                     "No payment was captured twice; the retry queue was drained after rollback.")
    builder.heading("Timeline")
    builder.bullet("09:12 - alerts fired for elevated 5xx responses.")
    builder.bullet("09:18 - on-call engineer reproduced the failure on the application host.")
    builder.bullet("09:41 - rollback completed and traffic returned to normal.")
    builder.heading("Follow-up")
    builder.para("Rotate the exposed credential, review deployment logging, and add a config check.")
    ctx.check("incident_timeline", True, {"start": ctx.scenario.timestamp(0) if ctx.scenario else "2026-03-18T09:12:00Z",
                                          "end": ctx.scenario.timestamp(10) if ctx.scenario else "2026-03-18T09:42:00Z"})
    return builder.build(header=cell("Internal"))


def _meeting_minutes(ctx: BuildContext) -> Doc:
    builder = DocBuilder("meeting_minutes", "Meeting minutes", "meeting_minutes.docx", ctx.doc_language)
    builder.heading("Platform weekly - meeting minutes")
    builder.para("Date: ", ctx.date("2026-03-18"), "  |  Location: internal video call")
    attendees = ctx.org.employees[:3]
    builder.heading("Attendees")
    for index, person in enumerate(attendees):
        builder.bullet(ctx.person_name(person, index), " - ", ctx.person_email(person, index))
    builder.heading("Notes")
    builder.para("The team reviewed the deployment checklist and the customer migration plan. "
                 "One action remains open for the database owner.")
    if ctx.wants("infrastructure"):
        builder.para("Migration target: ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint"),
                     " via ", ctx.shared("infrastructure", "internal_url", "url"))
    if ctx.wants("secrets"):
        builder.para("The shared integration key was pasted in chat during the demo: ",
                     ctx.shared("secrets", "api_key", "api_key"))
    if ctx.wants("payment"):
        builder.para("Finance noted a pending transaction: ",
                     ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    if ctx.rng.random() < 0.5:
        builder.heading("Risks")
        builder.para("The migration window overlaps a finance close. The team will confirm the rollback owner.")
    builder.heading("Action items")
    builder.bullet("Owner: ", ctx.person_name(attendees[1]), " - confirm the migration window.")
    builder.bullet("Owner: ", ctx.person_name(attendees[2]), " - remove the old deployment credential.")
    return builder.build(header=cell("Internal meeting notes"))


def _memo(ctx: BuildContext) -> Doc:
    builder = DocBuilder("internal_memo", "Internal memo", "internal_memo.docx", ctx.doc_language)
    builder.heading("Internal memo - access review")
    builder.para("To: ", ctx.person_name(ctx.org.employees[2]), "  |  From: ", ctx.person_name(ctx.org.employees[1]))
    builder.para("The quarterly access review found two accounts with elevated permissions. "
                 "Please confirm the owners before Friday.")
    if ctx.wants("pii"):
        builder.para("Account owner contact: ", ctx.person_email(ctx.org.employees[3]))
    if ctx.wants("secrets"):
        builder.para("Temporary review credential: ",
                     ctx.shared("secrets", "password", "review_password"))
    if ctx.wants("infrastructure"):
        builder.para("Review scope: ", ctx.shared("infrastructure", "private_network", "network"))
    builder.para("Memo.")
    return builder.build(header=cell("Internal memo"))


def _strategy_report(ctx: BuildContext) -> Doc:
    builder = DocBuilder("strategy_report", "Strategy report", "strategy_report.docx", ctx.doc_language)
    builder.heading("FY2026 strategy review")
    builder.para(f"{ctx.org.name} plans to expand its {ctx.org.industry} platform in the region.")
    builder.heading("Market view")
    builder.para("Customer demand grew in the mid-market segment. The team will prioritise retention "
                 "and shorten onboarding.")
    if ctx.wants("pii"):
        builder.para("Named customer sponsor: ", ctx.person_name(ctx.org.customers[0]),
                     " (", ctx.person_email(ctx.org.customers[0]), ")")
        builder.para("Customer address for the pilot: ", ctx.person_field(ctx.org.customers[0], "address", "pii", ["thai_address"]))
    if ctx.wants("payment"):
        builder.para("Expected booking: ", ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    if ctx.wants("infrastructure"):
        builder.para("Platform capacity: ", ctx.entity("infrastructure", ["system_architecture"]))
    builder.heading("Risks")
    builder.para("Dependency on a single vendor and limited local support capacity remain the top risks.")
    return builder.build(header=cell("Confidential strategy"))


def _risk_report(ctx: BuildContext) -> Doc:
    builder = DocBuilder("risk_report", "Risk report", "risk_report.docx", ctx.doc_language)
    builder.heading("Operational risk register")
    rows = [
        ["R-01", "Credential exposure in deployment logs", "high", "security"],
        ["R-02", "Database failover not tested", "medium", "platform"],
        ["R-03", "Vendor access review overdue", "medium", "compliance"],
    ]
    builder.table(["risk", "description", "rating", "owner"], rows, title="Risks")
    if ctx.wants("secrets"):
        builder.para("Example exposed value: ", ctx.shared("secrets", "api_key", "api_key"))
    if ctx.wants("infrastructure"):
        builder.para("Database endpoint in scope: ",
                     ctx.shared("infrastructure", "database_endpoint", "db_endpoint"))
    if ctx.wants("pii"):
        builder.para("Risk owner: ", ctx.person_name(ctx.org.employees[2]), " - ", ctx.person_email(ctx.org.employees[2]))
    return builder.build(header=cell("Risk committee"))


def _support_ticket(ctx: BuildContext) -> Doc:
    builder = DocBuilder("support_ticket", "Support ticket", "support_ticket.txt", ctx.doc_language)
    customer = ctx.org.customers[1]
    ticket_id = ctx.scenario.ticket_id if ctx.scenario else "#48219"
    builder.heading(f"Support ticket {ticket_id}")
    builder.para("Requester: ", ctx.person_name(customer, 1), " <", ctx.person_email(customer, 1), ">")
    if ctx.wants("pii"):
        builder.para("Phone: ", ctx.person_phone(customer, 1), "  Account: ", f"CUS-{ctx.rng.randint(100, 999)}")
    builder.para("Issue: after the latest release the checkout page shows an error. "
                 "The customer tried twice and is waiting for an update.")
    builder.para("Request ID: ", ctx.scenario.request_id(1) if ctx.scenario else "req-20482")
    if ctx.wants("infrastructure"):
        builder.para("Request from ", ctx.shared("infrastructure", "internal_ipv4", "ip_0"),
                     " to ", ctx.shared("infrastructure", "internal_url", "url"), " returned 502.")
    if ctx.wants("secrets"):
        builder.para("Browser console showed request header: ",
                     ctx.shared("secrets", "access_token", "access_token"))
    if ctx.wants("payment"):
        builder.para("Failed order reference: ",
                     ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    builder.para("Suggested next step: confirm the service health dashboard and review the gateway log.")
    return builder.build(header=cell("Support queue"))


def _customer_complaint(ctx: BuildContext) -> Doc:
    customer = ctx.org.customers[0]
    builder = DocBuilder("customer_complaint", "Customer complaint", "customer_complaint.txt", ctx.doc_language)
    builder.heading("Customer complaint - delayed delivery")
    builder.para("From: ", ctx.person_name(customer), " (", ctx.person_email(customer), ")")
    builder.para("Phone: ", ctx.person_phone(customer))
    if ctx.wants("pii"):
        builder.para("Delivery address: ", ctx.person_field(customer, "address", "pii", ["thai_address"]))
    builder.para("The parcel arrived three days late and the packaging was damaged. "
                 "Please confirm the replacement process.")
    if ctx.wants("payment"):
        builder.para("Order reference: ", ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    return builder.build()


def _leave_request(ctx: BuildContext) -> Doc:
    employee = ctx.org.employees[2]
    builder = DocBuilder("leave_request", "Leave request", "leave_request.docx", ctx.doc_language)
    builder.heading("Leave request form")
    builder.para("Employee: ", ctx.person_name(employee), "  |  Email: ", ctx.person_email(employee))
    if ctx.wants("pii"):
        builder.para("National ID: ", ctx.person_field(employee, "national_id", "pii", ["thai_national_id"]))
    builder.para("Leave type: annual  |  Dates: ", ctx.date("2026-04-06"), " to ",
                 ctx.date("2026-04-10"), "  |  Days: 5")
    builder.para("Reason: family trip. Coverage arranged with the platform team.")
    builder.para("Approved by: ", ctx.person_name(ctx.org.employees[0]))
    return builder.build(header=cell("HR form"))


def _candidate_evaluation(ctx: BuildContext) -> Doc:
    candidate = ctx.org.customers[2]
    builder = DocBuilder("candidate_evaluation", "Candidate evaluation", "candidate_evaluation.docx", ctx.doc_language)
    builder.heading("Candidate evaluation")
    builder.para("Candidate: ", ctx.person_name(candidate), " (", ctx.person_email(candidate), ")")
    builder.para("Role: data analyst  |  Interviewer: ", ctx.person_name(ctx.org.employees[1]))
    builder.table(["area", "rating", "notes"], [
        ["SQL", "strong", "clear explanations"],
        ["Stakeholder communication", "good", "structured examples"],
        ["Domain knowledge", "developing", "needs support"],
    ], title="Scorecard")
    return builder.build(header=cell("Hiring - confidential"))


def _medical_report(ctx: BuildContext) -> Doc:
    patient = ctx.org.customers[3]
    builder = DocBuilder("medical_report", "Medical report", "medical_report.docx", ctx.doc_language)
    builder.heading("Visit summary")
    builder.para("Patient: ", ctx.person_name(patient), "  |  HN: ", ctx.entity("pii", ["patient_id"]))
    if ctx.wants("pii"):
        builder.para("DOB: ", ctx.person_field(patient, "dob", "pii", ["date_of_birth"]),
                     "  Phone: ", ctx.person_phone(patient))
        builder.para("Diagnosis: ", ctx.entity("pii", ["health_condition"]))
    builder.para("Plan: routine follow-up in four weeks. No real medical advice is provided.")
    builder.para("Clinician: ", ctx.person_name(ctx.org.employees[4 % len(ctx.org.employees)]))
    return builder.build(header=cell("Medical record"))


def _lab_result(ctx: BuildContext) -> Doc:
    patient = ctx.org.customers[2]
    builder = DocBuilder("lab_result", "Laboratory result", "lab_result.pdf", ctx.doc_language)
    builder.heading("Laboratory result")
    builder.para("Patient: ", ctx.person_name(patient), "  |  HN: ", ctx.entity("pii", ["patient_id"]))
    builder.table(["test", "result", "reference"], [
        ["Haemoglobin", "13.2 g/dL", "12.0-16.0"],
        ["Fasting glucose", "98 mg/dL", "70-99"],
        ["Creatinine", "0.9 mg/dL", "0.6-1.1"],
    ], title="Results")
    builder.para("Laboratory result for internal review.")
    return builder.build(header=cell("Laboratory"))


def _prescription(ctx: BuildContext) -> Doc:
    patient = ctx.org.customers[1]
    builder = DocBuilder("prescription", "Prescription", "prescription.pdf", ctx.doc_language)
    builder.heading("Prescription")
    builder.para("Patient: ", ctx.person_name(patient), "  |  HN: ", ctx.entity("pii", ["patient_id"]))
    builder.table(["medication", "dose", "duration"], [
        ["Example medication A", "1 tablet daily", "7 days"],
        ["Example medication B", "as needed", "14 days"],
    ], title="Prescription")
    builder.para("Prescription for internal review.")
    return builder.build(header=cell("Prescription"))


def _visit_summary(ctx: BuildContext) -> Doc:
    return _medical_report(ctx)


def _architecture_notes(ctx: BuildContext) -> Doc:
    builder = DocBuilder("architecture_notes", "Architecture notes", "architecture_notes.md", ctx.doc_language)
    builder.heading("Order platform architecture")
    builder.para("Traffic enters through a public load balancer and reaches the API service. "
                 "Workers consume the queue and store results in PostgreSQL.")
    if ctx.wants("infrastructure"):
        builder.bullet("Edge router: ", ctx.shared("infrastructure", "internal_ipv4", "ip_0"))
        builder.bullet("API host: ", ctx.shared("infrastructure", "internal_hostname", "host_0"))
        builder.bullet("Database: ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint"))
        builder.bullet("Service URL: ", ctx.shared("infrastructure", "internal_url", "url"))
    if ctx.wants("secrets"):
        builder.para("The worker uses this integration credential: ",
                     ctx.shared("secrets", "api_key", "api_key"))
    if ctx.wants("pii"):
        builder.para("Platform owner: ", ctx.person_name(ctx.org.employees[0]), " (", ctx.person_email(ctx.org.employees[0]), ")")
    return builder.build(header=cell("Engineering notes"))


def _troubleshooting_notes(ctx: BuildContext) -> Doc:
    builder = DocBuilder("troubleshooting_notes", "Troubleshooting notes", "troubleshooting_notes.md", ctx.doc_language)
    builder.heading("Troubleshooting notes - prod database")
    builder.para("Symptom: the API starts but readiness checks fail. Local environment works.")
    if ctx.wants("infrastructure"):
        builder.bullet("Resolved database endpoint: ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint"))
        builder.bullet("Application host: ", ctx.shared("infrastructure", "internal_ipv4", "ip_0"))
        builder.bullet("Internal service: ", ctx.shared("infrastructure", "internal_url", "url"))
    if ctx.wants("secrets"):
        builder.para("The current environment file contains: ",
                     ctx.shared("secrets", "database_credential", "db_credential"))
    if ctx.wants("payment"):
        builder.para("A payment retry job is also failing: ",
                     ctx.shared("payment", "payment_transaction_reference", "txn_0"))
    builder.para("Next step: verify DNS resolution and the database security group.")
    return builder.build()


# --------------------------------------------------------------------------
# Configuration, code, logs and structured payloads
# --------------------------------------------------------------------------


def _env_config(ctx: BuildContext) -> Doc:
    builder = DocBuilder("application_environment_config", "Application environment", "prod.env", ctx.doc_language)
    builder.heading("Production environment")
    record: Dict[str, Any] = {
        "APP_ENV": "production",
        "APP_PORT": "8080",
        "LOG_LEVEL": "info",
    }
    if ctx.wants("infrastructure"):
        record["DB_HOST"] = ctx.shared("infrastructure", "database_endpoint", "db_endpoint")
        record["REDIS_HOST"] = ctx.shared("infrastructure", "internal_hostname", "host_1")
        record["API_BASE_URL"] = ctx.shared("infrastructure", "internal_url", "url")
    if ctx.wants("secrets"):
        record["DB_USER"] = "example_app"
        record["DB_PASSWORD"] = ctx.shared("secrets", "password", "db_password")
        record["API_KEY"] = ctx.shared("secrets", "api_key", "api_key")
        record["JWT_SECRET"] = ctx.shared("secrets", "jwt_token", "jwt")
    builder.record(record)
    builder.para("Never commit real environment files. This example is non-functional.")
    return builder.build()


def _app_config(ctx: BuildContext) -> Doc:
    builder = DocBuilder("application_config", "Application configuration", "application.yaml", ctx.doc_language)
    builder.heading("Application configuration")
    record: Dict[str, Any] = {
        "app": {"name": "orders-api", "environment": "production", "port": 8080},
        "logging": {"level": "info", "destination": "stdout"},
    }
    database: Dict[str, Any] = {"engine": "postgresql", "port": 5432}
    if ctx.wants("infrastructure"):
        database["host"] = ctx.shared("infrastructure", "database_endpoint", "db_endpoint")
        database["replica"] = ctx.shared("infrastructure", "internal_hostname", "host_1")
        record["service_url"] = ctx.shared("infrastructure", "internal_url", "url")
    if ctx.wants("secrets"):
        database["username"] = "example_app"
        database["password"] = ctx.shared("secrets", "password", "db_password")
        record["api_key"] = ctx.shared("secrets", "api_key", "api_key")
    record["database"] = database
    builder.record(record)
    return builder.build()


def _k8s_manifest(ctx: BuildContext) -> Doc:
    builder = DocBuilder("kubernetes_manifest", "Kubernetes deployment", "deployment.yaml", ctx.doc_language)
    builder.heading("Kubernetes deployment")
    record: Dict[str, Any] = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "orders-api", "namespace": f"{ctx.org.slug}-prod"},
        "spec": {"replicas": 3, "selector": {"matchLabels": {"app": "orders-api"}}},
    }
    env: List[Any] = [{"name": "APP_ENV", "value": "production"}]
    if ctx.wants("secrets"):
        env.append({"name": "DB_PASSWORD", "value": ctx.shared("secrets", "password", "db_password")})
        env.append({"name": "API_KEY", "value": ctx.shared("secrets", "api_key", "api_key")})
    if ctx.wants("infrastructure"):
        env.append({"name": "DB_HOST", "value": ctx.shared("infrastructure", "database_endpoint", "db_endpoint")})
    record["spec"]["template"] = {"spec": {"containers": [{"name": "api", "image": f"registry.{ctx.org.slug}.example/orders:1.4.2", "env": env}]}}
    builder.record(record)
    return builder.build()


def _docker_compose(ctx: BuildContext) -> Doc:
    builder = DocBuilder("docker_compose", "Docker Compose", "docker-compose.yaml", ctx.doc_language)
    builder.heading("Docker Compose stack")
    record: Dict[str, Any] = {
        "version": "3.9",
        "services": {
            "api": {"image": "example/orders-api:1.4.2", "ports": ["8080:8080"]},
            "worker": {"image": "example/orders-worker:1.4.2"},
        },
    }
    if ctx.wants("secrets"):
        record["services"]["api"]["environment"] = {
            "DB_PASSWORD": ctx.shared("secrets", "password", "db_password"),
            "API_KEY": ctx.shared("secrets", "api_key", "api_key"),
        }
    if ctx.wants("infrastructure"):
        record["services"]["api"]["environment"] = record["services"]["api"].get("environment", {})
        record["services"]["api"]["environment"]["DB_HOST"] = ctx.shared(
            "infrastructure", "database_endpoint", "db_endpoint")
    builder.record(record)
    return builder.build()


def _terraform_config(ctx: BuildContext) -> Doc:
    builder = DocBuilder("terraform_config", "Terraform configuration", "main.tf", ctx.doc_language)
    builder.heading("Terraform configuration")
    lines: List[Any] = [
        'provider "aws" { region = "ap-southeast-1" }',
        'resource "aws_db_instance" "main" {',
        '  engine         = "postgres"',
        '  instance_class = "db.t3.medium"',
    ]
    if ctx.wants("infrastructure"):
        lines.append(["  identifier = \"", ctx.shared("infrastructure", "internal_hostname", "host_0"), "\""])
    if ctx.wants("secrets"):
        lines.append(["  password   = \"", ctx.shared("secrets", "password", "db_password"), "\""])
    lines.append("  skip_final_snapshot = true")
    lines.append("}")
    builder.code(lines)
    return builder.build()


def _database_config(ctx: BuildContext) -> Doc:
    builder = DocBuilder("database_config", "Database configuration", "database.ini", ctx.doc_language)
    builder.heading("Database configuration")
    record: Dict[str, Any] = {"database": {"engine": "postgresql", "port": 5432, "pool_size": 20}}
    if ctx.wants("infrastructure"):
        record["database"]["host"] = ctx.shared("infrastructure", "database_endpoint", "db_endpoint")
    if ctx.wants("secrets"):
        record["database"]["user"] = "example_app"
        record["database"]["password"] = ctx.shared("secrets", "password", "db_password")
    record["database"]["ssl_mode"] = "require"
    builder.record(record)
    return builder.build()


def _service_account_config(ctx: BuildContext) -> Doc:
    builder = DocBuilder("service_account_config", "Service account", "service_account.json", ctx.doc_language)
    builder.heading("Service account configuration")
    record: Dict[str, Any] = {
        "type": "service_account",
        "project_id": "example-fake-project",
        "client_email": f"test-service@{ctx.org.slug}.example",
        "token_uri": "https://oauth2.example.invalid/token",
    }
    if ctx.wants("secrets"):
        record["private_key"] = ctx.entity("secrets", ["service_account_credential"])
        record["client_secret"] = ctx.entity("secrets", ["oauth_client_secret"])
    builder.record(record)
    return builder.build()


def _api_payload(ctx: BuildContext) -> Doc:
    builder = DocBuilder("api_payload", "API payload", "api_payload.json", ctx.doc_language)
    builder.heading("Webhook payload")
    record: Dict[str, Any] = {
        "event": "order.created",
        "id": f"evt_{ctx.rng.randint(100000, 999999)}",
        "created_at": "2026-03-18T09:12:44Z",
    }
    customer: Dict[str, Any] = {"id": f"CUS-{ctx.rng.randint(1000, 9999)}"}
    if ctx.wants("pii"):
        person = ctx.org.customers[0]
        customer.update({"name": ctx.person_name(person), "email": ctx.person_email(person), "phone": ctx.person_phone(person)})
    if ctx.wants("payment"):
        customer.update({
            "card": ctx.entity("payment", ["payment_card_number"]),
            "expiry": ctx.entity("payment", ["card_expiry_date"]),
            "transaction": ctx.entity("payment", ["payment_transaction_reference"]),
        })
    record["customer"] = customer
    if ctx.wants("secrets"):
        record["signature"] = ctx.shared("secrets", "webhook_secret", "webhook_secret")
    if ctx.wants("infrastructure"):
        record["source_ip"] = ctx.shared("infrastructure", "internal_ipv4", "ip_0")
    builder.record(record)
    return builder.build(xml_root="event")


def _xml_export(ctx: BuildContext) -> Doc:
    builder = DocBuilder("xml_export", "Customer export", "customer_export.xml", ctx.doc_language)
    builder.heading("Customer export")
    customer = ctx.org.customers[1]
    record: Dict[str, Any] = {"exported_at": "2026-03-18T09:12:44Z"}
    if ctx.wants("pii"):
        customer = ctx.org.customers[1]
        record["customer"] = {"name": ctx.person_name(customer), "email": ctx.person_email(customer), "phone": ctx.person_phone(customer)}
    if ctx.wants("payment"):
        record["payment"] = {
            "card": ctx.entity("payment", ["payment_card_number"]),
            "amount": "12,400.00",
            "reference": ctx.entity("payment", ["payment_transaction_reference"]),
        }
    if ctx.wants("secrets"):
        record["token"] = ctx.shared("secrets", "access_token", "access_token")
    builder.record(record)
    return builder.build(xml_root="customerExport")


def _sql_export(ctx: BuildContext) -> Doc:
    builder = DocBuilder("sql_export", "SQL export", "customer_export.sql", ctx.doc_language)
    builder.heading("SQL export")
    lines: List[Any] = ["CREATE TABLE customers (id text, name text, email text, phone text);"]
    for index in range(3):
        person = ctx.org.customers[index]
        lines.append([
            "INSERT INTO customers VALUES ('CUS-", str(1000 + index), "', '",
            ctx.person_name(person, index), "', '", ctx.person_email(person, index), "', '", ctx.person_phone(person, index), "');",
        ])
    if ctx.wants("payment"):
        lines.append(["INSERT INTO payments VALUES ('", ctx.shared("payment", "payment_transaction_reference", "txn_0"),
                      "', '", ctx.shared("payment", "payment_card_number", "corp_card"), "');"])
    if ctx.wants("secrets"):
        lines.append(["INSERT INTO config VALUES ('API_KEY', '",
                      ctx.shared("secrets", "api_key", "api_key"), "');"])
    builder.code(lines)
    return builder.build()


def _source_code(ctx: BuildContext, language: str = "py") -> Doc:
    ext = language
    builder = DocBuilder("source_code", "Application source", f"app.{ext}", ctx.doc_language)
    builder.heading("Application source")
    if ext == "py":
        lines: List[Any] = [
            "import os",
            "import requests",
            "",
            "DB_HOST = ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint") if ctx.wants("infrastructure") else "os.getenv('DB_HOST')",
            "API_KEY = ", ctx.shared("secrets", "api_key", "api_key") if ctx.wants("secrets") else "os.getenv('API_KEY')",
            "",
            "def fetch_customer(customer_id):",
            "    url = f\"https://api.example.org/v1/customers/{customer_id}\"",
            "    return requests.get(url, headers={'Authorization': API_KEY}, timeout=10)",
            "",
            "if __name__ == '__main__':",
            "    print(fetch_customer('CUS-1042').status_code)",
        ]
    elif ext in ("js", "ts"):
        lines = [
            "const axios = require('axios');",
            "const dbHost = '",
            ctx.shared("infrastructure", "database_endpoint", "db_endpoint") if ctx.wants("infrastructure") else "localhost",
            "';",
            "const apiKey = '",
            ctx.shared("secrets", "api_key", "api_key") if ctx.wants("secrets") else "process.env.API_KEY",
            "';",
            "async function fetchCustomer(id) {",
            "  return axios.get(`https://api.example.org/v1/customers/${id}`, { headers: { Authorization: apiKey } });",
            "}",
        ]
    elif ext == "go":
        lines = [
            "package main",
            'import ("fmt"; "net/http")',
            'const dbHost = "',
            ctx.shared("infrastructure", "database_endpoint", "db_endpoint") if ctx.wants("infrastructure") else "localhost",
            '"',
            'const apiKey = "',
            ctx.shared("secrets", "api_key", "api_key") if ctx.wants("secrets") else "example",
            '"',
            "func main() { fmt.Println(dbHost, apiKey) }",
        ]
    elif ext == "java":
        lines = [
            "public class App {",
            '  private static final String DB_HOST = "',
            ctx.shared("infrastructure", "database_endpoint", "db_endpoint") if ctx.wants("infrastructure") else "localhost",
            '";',
            '  private static final String API_KEY = "',
            ctx.shared("secrets", "api_key", "api_key") if ctx.wants("secrets") else "example",
            '";',
            "  public static void main(String[] args) { System.out.println(DB_HOST); }",
            "}",
        ]
    else:
        lines = ["# source file", "API_KEY=example"]
    if not any(isinstance(part, Entity) for line in lines
               for part in (line if isinstance(line, (list, tuple)) else [line])):
        # A code screenshot without any entity would carry no OCR ground truth;
        # a maintainer contact in a comment is realistic and keeps the case useful.
        lines.append(["# contact: ", ctx.person_email(ctx.org.employees[0])])
    builder.code(lines)
    return builder.build()


def _log_lines(ctx: BuildContext, kind: str) -> Doc:
    builder = DocBuilder(kind, "Application log", f"{kind}.log", ctx.doc_language)
    builder.heading(f"{kind}")
    log_format = ctx.rng.choice(("iso", "iso", "bracket", "json"))

    def infra(types: Sequence[str], key: str, fallback: str) -> Any:
        return ctx.shared("infrastructure", types[0], key) if ctx.wants("infrastructure") else fallback

    def stamp(index: int) -> str:
        if ctx.scenario is not None:
            return ctx.scenario.format_timestamp(index, log_format)
        if log_format == "bracket":
            return f"2026/03/18 {9 + index // 60:02d}:{12 + index * 3:02d}:{(index * 7) % 60:02d} +0000"
        return f"2026-03-18T09:{12 + index * 3:02d}:{(index * 7) % 60:02d}Z"

    def row(index: int) -> List[Any]:
        person = ctx.org.employees[index % len(ctx.org.employees)]
        timestamp = stamp(index)
        request_id = ctx.scenario.request_id(index) if ctx.scenario else f"req-{10000 + index}"
        if kind == "auth_log":
            parts: List[Any] = [timestamp, " INFO auth ", ctx.person_email(person, index), " from ",
                                infra(["internal_ipv4"], f"ip_{index % 4}", "192.0.2.10"),
                                " result=success request_id=", request_id]
        elif kind == "api_gateway_log":
            parts = [timestamp, " INFO gateway method=POST path=",
                     infra(["internal_url"], "url", "/api/v1/orders"),
                     " status=502 source=", infra(["internal_ipv4"], f"ip_{index % 4}", "192.0.2.10"),
                     " request_id=", request_id]
        elif kind == "deployment_log":
            parts = [timestamp, " INFO deploy host=",
                     infra(["internal_hostname"], f"host_{index % 4}", "app-host"),
                     " image=orders-api:1.4.2 status=started db=",
                     infra(["database_endpoint"], "db_endpoint", "db.example.org:5432"),
                     " request_id=", request_id]
        else:
            parts = [timestamp, " INFO worker request_id=", request_id,
                     " user=", ctx.person_email(person, index), " client_ip=",
                     infra(["internal_ipv4"], f"ip_{index % 4}", "192.0.2.10"),
                     ' msg="order processed"']
        if log_format == "json":
            return ['{"ts":"', timestamp, '","level":"INFO","service":"', kind,
                    '","user":"', ctx.person_email(person, index),
                    '","request_id":"', request_id,
                    '","db":"', infra(["database_endpoint"], "db_endpoint", "db.example.org:5432"),
                    '","msg":"order processed"}']
        return parts

    lines: List[Any] = [row(index) for index in range(8)]
    if ctx.wants("secrets"):
        # The failure is the last event on the shared timeline, never a
        # hardcoded wall-clock value.
        error_stamp = stamp(8)
        if log_format == "json":
            lines.append(['{"ts":"', error_stamp, '","level":"ERROR","service":"', kind,
                          '","msg":"auth failed","key":"',
                          ctx.shared("secrets", "api_key", "api_key"), '"}'])
        else:
            lines.append([error_stamp, " ERROR auth failed for key ",
                          ctx.shared("secrets", "api_key", "api_key"), " retry=true"])
    builder.log(lines)
    rendered = builder.doc.blocks[-1].text
    result = validate_log_order(rendered.splitlines())
    ctx.check("log_timestamps_ordered", result["status"], {
        "entries": len(lines), "format": log_format,
        "first": result.get("first"), "last": result.get("last"),
        "reason": result.get("reason", ""),
    }, evaluated_items=result["evaluated_items"])
    return builder.build()


def _slide_deck(ctx: BuildContext, kind: str) -> Doc:
    builder = DocBuilder(kind, kind.replace("_", " ").title(), f"{kind}.pptx", ctx.doc_language)
    titles = {
        "management_deck": ["Q1 business review", "Customer growth", "Platform investment", "Next quarter"],
        "architecture_deck": ["Order platform", "Network layout", "Data layer", "Open risks"],
        "incident_review_deck": ["Incident review", "Timeline", "Root cause", "Actions"],
        "sales_report_deck": ["Sales performance", "Pipeline", "Customer examples", "Forecast"],
    }.get(kind, ["Overview", "Details", "Risks", "Next steps"])
    for index, title in enumerate(titles):
        if index == 0:
            builder.slide(title, "Management presentation.")
        elif index == 1:
            parts: List[Any] = ["The team reviewed operational performance and customer feedback."]
            if ctx.wants("pii"):
                parts += ["Customer sponsor: ", ctx.person_name(ctx.org.customers[0]),
                          " (", ctx.person_email(ctx.org.customers[0]), ")."]
            builder.slide(title, *parts)
        elif index == 2:
            parts = ["Platform capacity and controls remain the main focus."]
            if ctx.wants("infrastructure"):
                parts += ["Database: ", ctx.shared("infrastructure", "database_endpoint", "db_endpoint"),
                          " Host: ", ctx.shared("infrastructure", "internal_hostname", "host_0"), "."]
            if ctx.wants("secrets"):
                parts += ["Legacy integration key still present in the deployment job: ",
                          ctx.shared("secrets", "api_key", "api_key"), "."]
            builder.slide(title, *parts)
        else:
            builder.slide(title, "Actions: confirm owners, rotate credentials, and complete the review.")
    return builder.build()


def _screenshot_doc(ctx: BuildContext, kind: str) -> Doc:
    if kind == "screenshot_terminal":
        doc = _log_lines(ctx, "deployment_log")
        doc.metadata["image_style"] = "terminal"
    elif kind == "screenshot_config":
        doc = _env_config(ctx)
        doc.metadata["image_style"] = "config"
    elif kind == "screenshot_dashboard":
        doc = _sales_pipeline(ctx)
        doc.metadata["image_style"] = "dashboard"
    elif kind == "screenshot_email":
        doc = _support_ticket(ctx)
        doc.metadata["image_style"] = "email"
    elif kind == "screenshot_chat":
        doc = _meeting_minutes(ctx)
        doc.metadata["image_style"] = "chat"
    elif kind == "screenshot_receipt":
        doc = _finance_document(ctx, "invoice")
        doc.metadata["image_style"] = "receipt"
    elif kind == "screenshot_form":
        doc = _leave_request(ctx)
        doc.metadata["image_style"] = "form"
    elif kind == "screenshot_id":
        doc = _id_card_doc(ctx)
        doc.metadata["image_style"] = "id_card"
    else:
        doc = _source_code(ctx, "py")
        doc.metadata["image_style"] = "code"
    doc.metadata["ocr_difficulty"] = ctx.ocr_difficulty
    doc.metadata["image_seed"] = ctx.rng.randint(0, 10**9)
    return doc


def _id_card_doc(ctx: BuildContext) -> Doc:
    person = ctx.org.employees[0]
    builder = DocBuilder("screenshot_id", "Employee ID sample", "employee_id.png", ctx.doc_language)
    builder.heading("Employee identity sample")
    builder.para("Name: ", ctx.person_name(person))
    builder.para("ID: ", ctx.entity("pii", ["thai_national_id"]))
    builder.para("DOB: ", ctx.person_field(person, "dob", "pii", ["date_of_birth"]))
    builder.para("Address: ", ctx.person_field(person, "address", "pii", ["thai_address"]))
    builder.para("Internal employee identity record.")
    return builder.build()


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


def _a(id, label, category, domains, renderers, difficulty, builder, rationale, tags=()) -> Archetype:
    return Archetype(id, label, category, tuple(domains), tuple(renderers), difficulty, builder, rationale, tuple(tags))


ARCHETYPES: List[Archetype] = [
    _a("employee_list", "Employee list", "HR", ["pii", "payment", "infrastructure"], TABLE_RENDERERS, 3,
       _employee_list, "Employee directory with names, contact details and optional identifiers."),
    _a("payroll", "Payroll register", "HR", ["pii", "payment", "secrets"], ("xlsx", "csv", "pdf", "docx"), 4,
       _payroll, "Payroll workbook with bank details and salary amounts."),
    _a("customer_export", "Customer export", "CRM", ["pii", "payment"], ("csv", "xlsx", "json", "xml"), 3,
       _customer_export, "Customer export with contact data and optional card on file."),
    _a("transaction_export", "Transaction export", "Finance", ["payment", "pii"], ("csv", "xlsx", "json", "xml"), 3,
       _transaction_export, "Payment transaction export with card and customer fields."),
    _a("patient_list", "Patient list", "Healthcare", ["pii"], ("xlsx", "csv", "pdf"), 4,
       _patient_list, "Fictional clinic appointment list with patient identifiers."),
    _a("server_inventory", "Server inventory", "IT", ["infrastructure", "pii"], ("csv", "xlsx", "md", "txt"), 3,
       _server_inventory, "Hosts, private addresses and owner emails."),
    _a("sales_pipeline", "Sales pipeline", "Sales", ["pii", "payment"], ("xlsx", "csv"), 3,
       _sales_pipeline, "Opportunity list with customer contacts and payment references."),
    _a("access_records", "Access records", "IT", ["pii", "infrastructure"], ("csv", "xlsx", "log"), 3,
       _access_records, "Authentication/access export with users, IPs and resources."),
    _a("vendor_list", "Vendor list", "Operations", ["pii"], ("xlsx", "csv"), 2,
       _vendor_list, "Vendor contacts with business identifiers."),
    _a("bank_statement", "Bank statement", "Finance", ["payment", "pii"], ("pdf", "csv", "xlsx"), 3,
       _bank_statement, "Synthetic statement with transaction references."),
    _a("expense_report", "Expense report", "Finance", ["payment", "pii"], ("xlsx", "csv", "pdf"), 3,
       _expense_report, "Employee expense claim with card data."),
    _a("appointment_list", "Appointment list", "Healthcare", ["pii"], ("xlsx", "csv", "pdf"), 3,
       _appointment_list, "Clinic appointment list."),
    _a("order_export", "Order export", "Operations", ["pii"], ("csv", "xlsx"), 2,
       _order_export, "Order export with customer contact and delivery details."),
    _a("invoice", "Invoice", "Finance", ["payment", "pii", "secrets", "infrastructure"], ("pdf", "docx", "xlsx"), 4,
       lambda ctx: _finance_document(ctx, "invoice"), "Invoice with consistent line items, totals and payment data."),
    _a("quotation", "Quotation", "Finance", ["payment", "pii"], ("pdf", "docx", "xlsx"), 3,
       lambda ctx: _finance_document(ctx, "quotation"), "Quotation with customer and payment references."),
    _a("purchase_order", "Purchase order", "Finance", ["payment", "pii"], ("pdf", "docx", "csv"), 3,
       lambda ctx: _finance_document(ctx, "purchase_order"), "Purchase order with vendor and payment data."),
    _a("employment_contract", "Employment contract", "HR", ["pii", "payment", "secrets"], ("docx", "pdf"), 4,
       lambda ctx: _contract(ctx, "employment_contract"), "Employment contract with personal and bank details."),
    _a("nda", "NDA", "HR", ["pii", "secrets"], ("docx", "pdf"), 3,
       lambda ctx: _contract(ctx, "nda"), "NDA with parties and a legacy credential reference."),
    _a("supplier_agreement", "Supplier agreement", "Finance", ["pii", "payment", "secrets"], ("docx", "pdf"), 4,
       lambda ctx: _contract(ctx, "supplier_agreement"), "Supplier agreement with bank and contact data."),
    _a("customer_contract", "Customer contract", "Sales", ["pii", "payment"], ("docx", "pdf"), 4,
       lambda ctx: _contract(ctx, "customer_contract"), "Customer contract with contact and billing details."),
    _a("cv", "CV / resume", "HR", ["pii"], ("docx", "pdf", "txt", "md"), 2,
       _cv, "Candidate CV with contact and identity details."),
    _a("incident_report", "Incident report", "IT", ["pii", "infrastructure", "secrets", "payment"], ("docx", "pdf", "md", "txt"), 4,
       _incident_report, "Multi-domain incident report: reporter, hosts, credentials and payment retries."),
    _a("meeting_minutes", "Meeting minutes", "Management", ["pii", "infrastructure", "secrets", "payment"], ("docx", "pdf", "md", "txt"), 3,
       _meeting_minutes, "Meeting notes with attendees, internal systems and leaked credentials."),
    _a("internal_memo", "Internal memo", "Management", ["pii", "secrets", "infrastructure"], ("docx", "pdf", "md", "txt"), 2,
       _memo, "Short internal memo with access-review context."),
    _a("strategy_report", "Strategy report", "Management", ["pii", "payment", "infrastructure"], ("docx", "pdf", "pptx"), 4,
       _strategy_report, "Corporate strategy report with customer and platform context."),
    _a("risk_report", "Risk report", "Management", ["secrets", "infrastructure", "pii"], ("docx", "pdf"), 3,
       _risk_report, "Risk register referencing systems, owners and exposed credentials."),
    _a("support_ticket", "Support ticket", "Operations", ["pii", "infrastructure", "secrets", "payment"], ("txt", "md", "json", "docx"), 3,
       _support_ticket, "Support conversation with requester, logs and credentials."),
    _a("customer_complaint", "Customer complaint", "Operations", ["pii", "payment"], ("txt", "docx", "md"), 2,
       _customer_complaint, "Customer complaint with delivery/payment context."),
    _a("leave_request", "Leave request", "HR", ["pii"], ("docx", "pdf", "txt"), 2,
       _leave_request, "HR form with identity fields."),
    _a("candidate_evaluation", "Candidate evaluation", "HR", ["pii"], ("docx", "pdf"), 2,
       _candidate_evaluation, "Hiring scorecard with candidate identity."),
    _a("medical_report", "Medical report", "Healthcare", ["pii"], ("docx", "pdf"), 4,
       _medical_report, "Fictional visit summary with health data."),
    _a("lab_result", "Lab result", "Healthcare", ["pii"], ("pdf", "docx"), 3,
       _lab_result, "Fictional lab result with patient identifiers."),
    _a("prescription", "Prescription", "Healthcare", ["pii"], ("pdf", "docx"), 3,
       _prescription, "Fictional prescription with patient identifiers."),
    _a("visit_summary", "Visit summary", "Healthcare", ["pii"], ("docx", "pdf"), 3,
       _visit_summary, "Fictional medical visit summary."),
    _a("architecture_notes", "Architecture notes", "IT", ["infrastructure", "secrets", "pii"], ("md", "txt", "docx", "pdf"), 3,
       _architecture_notes, "Engineering notes with hosts, endpoints and owner contacts."),
    _a("troubleshooting_notes", "Troubleshooting notes", "IT", ["infrastructure", "secrets", "payment"], ("md", "txt"), 3,
       _troubleshooting_notes, "Debug notes with database endpoints and credentials."),
    _a("application_environment_config", "Environment config", "IT", ["secrets", "infrastructure"], ("env", "txt", "conf", "ini", "toml"), 2,
       _env_config, "Production .env with fake credentials and private endpoints."),
    _a("application_config", "Application config", "IT", ["secrets", "infrastructure"], CONFIG_RENDERERS, 3,
       _app_config, "YAML/JSON application configuration with database and API credentials."),
    _a("kubernetes_manifest", "Kubernetes manifest", "IT", ["infrastructure", "secrets"], ("yaml", "yml", "json", "txt", "md"), 3,
       _k8s_manifest, "Kubernetes deployment with env credentials and private endpoints."),
    _a("docker_compose", "Docker Compose", "IT", ["infrastructure", "secrets"], ("yaml", "yml", "json", "txt", "md"), 3,
       _docker_compose, "Docker Compose stack with fake environment secrets."),
    _a("terraform_config", "Terraform config", "IT", ["infrastructure", "secrets"], ("tf", "txt", "md"), 3,
       _terraform_config, "Terraform configuration with synthetic database credentials."),
    _a("database_config", "Database config", "IT", ["secrets", "infrastructure"], ("ini", "conf", "toml", "env", "txt"), 2,
       _database_config, "Database configuration with credentials."),
    _a("service_account_config", "Service account config", "IT", ["secrets"], ("json", "yaml", "yml", "txt"), 3,
       _service_account_config, "Service-account-like configuration with fake key material."),
    _a("api_payload", "API payload", "IT", ["pii", "payment", "secrets", "infrastructure"], ("json", "xml", "txt", "md"), 3,
       _api_payload, "Webhook payload mixing customer, payment and signing data."),
    _a("xml_export", "XML export", "Finance", ["pii", "payment", "secrets"], ("xml", "txt"), 3,
       _xml_export, "Legacy XML export with customer and payment elements."),
    _a("sql_export", "SQL export", "IT", ["pii", "payment", "secrets"], ("sql", "txt"), 3,
       _sql_export, "SQL insert statements containing synthetic customer rows."),
    _a("source_code", "Source code", "IT", ["secrets", "infrastructure"], CODE_RENDERERS, 3,
       lambda ctx: _source_code(ctx, "py"), "Application code with embedded fake key and DB endpoint."),
    _a("source_code_js", "JavaScript source", "IT", ["secrets", "infrastructure"], ("js", "ts", "txt", "md"), 3,
       lambda ctx: _source_code(ctx, "js"), "JavaScript source with embedded fake key and DB endpoint."),
    _a("source_code_go", "Go source", "IT", ["secrets", "infrastructure"], ("go", "txt", "md"), 3,
       lambda ctx: _source_code(ctx, "go"), "Go source with embedded fake key and DB endpoint."),
    _a("source_code_java", "Java source", "IT", ["secrets", "infrastructure"], ("java", "txt", "md"), 3,
       lambda ctx: _source_code(ctx, "java"), "Java source with embedded fake key and DB endpoint."),
    _a("app_log", "Application log", "IT", ["infrastructure", "pii", "secrets"], LOG_RENDERERS, 3,
       lambda ctx: _log_lines(ctx, "app_log"), "Application log with users, IPs and a leaked credential."),
    _a("auth_log", "Auth log", "IT", ["pii", "infrastructure"], LOG_RENDERERS, 3,
       lambda ctx: _log_lines(ctx, "auth_log"), "Authentication log with user emails and private IPs."),
    _a("api_gateway_log", "API gateway log", "IT", ["infrastructure", "pii"], LOG_RENDERERS, 3,
       lambda ctx: _log_lines(ctx, "api_gateway_log"), "Gateway log with endpoints and source addresses."),
    _a("deployment_log", "Deployment log", "IT", ["infrastructure", "secrets"], LOG_RENDERERS, 3,
       lambda ctx: _log_lines(ctx, "deployment_log"), "Deployment log with hosts, database endpoints and a credential."),
    _a("management_deck", "Management deck", "Management", ["pii", "infrastructure", "secrets"], SLIDE_RENDERERS, 4,
       lambda ctx: _slide_deck(ctx, "management_deck"), "Board-style deck with later-slide sensitive data."),
    _a("architecture_deck", "Architecture deck", "IT", ["infrastructure", "secrets"], SLIDE_RENDERERS, 3,
       lambda ctx: _slide_deck(ctx, "architecture_deck"), "Architecture presentation with hosts and endpoints."),
    _a("incident_review_deck", "Incident review deck", "IT", ["pii", "infrastructure", "secrets"], SLIDE_RENDERERS, 4,
       lambda ctx: _slide_deck(ctx, "incident_review_deck"), "Incident-review presentation."),
    _a("sales_report_deck", "Sales report deck", "Sales", ["pii", "payment"], SLIDE_RENDERERS, 3,
       lambda ctx: _slide_deck(ctx, "sales_report_deck"), "Sales deck with customer and payment references."),
    _a("screenshot_terminal", "Terminal screenshot", "IT", ["infrastructure", "secrets", "pii"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_terminal"), "OCR test image of deployment output."),
    _a("screenshot_config", "Config screenshot", "IT", ["secrets", "infrastructure"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_config"), "OCR test image of an environment file."),
    _a("screenshot_dashboard", "Dashboard screenshot", "Sales", ["pii", "payment"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_dashboard"), "OCR test image of a CRM dashboard."),
    _a("screenshot_email", "Email screenshot", "Operations", ["pii", "infrastructure"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_email"), "OCR test image of a support email."),
    _a("screenshot_chat", "Chat screenshot", "Operations", ["pii", "secrets"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_chat"), "OCR test image of a workplace chat."),
    _a("screenshot_receipt", "Receipt screenshot", "Finance", ["payment", "pii"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_receipt"), "OCR test image of a receipt."),
    _a("screenshot_form", "Form screenshot", "HR", ["pii"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_form"), "OCR test image of a leave form."),
    _a("screenshot_id", "Synthetic ID screenshot", "HR", ["pii"], IMAGE_RENDERERS, 4,
       lambda ctx: _screenshot_doc(ctx, "screenshot_id"), "Fictional ID-like image, clearly marked synthetic."),
    _a("screenshot_code", "Source screenshot", "IT", ["secrets", "infrastructure"], IMAGE_RENDERERS, 3,
       lambda ctx: _screenshot_doc(ctx, "screenshot_code"), "OCR test image of source code."),
    _a("scanned_invoice", "Scanned invoice", "Finance", ["payment", "pii"], ("pdf",), 4,
       lambda ctx: _scanned(ctx, "invoice"), "Scanned PDF: image-only invoice with OCR ground truth."),
    _a("scanned_medical_report", "Scanned medical report", "Healthcare", ["pii"], ("pdf",), 4,
       lambda ctx: _scanned(ctx, "medical"), "Scanned PDF: image-only medical report."),
]


def _scanned(ctx: BuildContext, kind: str) -> Doc:
    if kind == "medical":
        doc = _medical_report(ctx)
        doc.filename = "medical_report_scan.pdf"
        doc.metadata["image_style"] = "scan"
    else:
        doc = _finance_document(ctx, "invoice")
        doc.filename = "invoice_scan.pdf"
        doc.metadata["image_style"] = "receipt"
    doc.scan = True
    doc.metadata["ocr_difficulty"] = ctx.ocr_difficulty
    doc.metadata["image_seed"] = ctx.rng.randint(0, 10**9)
    return doc


BY_ID = {archetype.id: archetype for archetype in ARCHETYPES}


def for_renderer(renderer: str) -> List[Archetype]:
    return [item for item in ARCHETYPES if renderer in item.renderers]


def for_domains(domains: Sequence[str], renderer: Optional[str] = None) -> List[Archetype]:
    wanted = set(domains)
    pool = [item for item in ARCHETYPES if wanted.intersection(item.domains)]
    if renderer:
        pool = [item for item in pool if renderer in item.renderers]
    return pool
