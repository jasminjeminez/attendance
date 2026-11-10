"""
Employee Attendance Recording System
Python (Flask) + sqlite3 + Bootstrap 5

Run:
    pip install flask
    python app.py
Open: http://127.0.0.1:5000

Bootstrap: uses static/bootstrap.min.css if it exists (offline),
otherwise falls back to the CDN link (needs internet).
"""
import os
import sqlite3
from datetime import datetime

from flask import Flask, g, render_template, request, redirect, url_for, flash
from jinja2 import DictLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "Attendance.db")
LOCAL_CSS = os.path.join(BASE_DIR, "static", "bootstrap.min.css")

app = Flask(__name__)
app.secret_key = "skilltest"


# ----------------------------------------------------------------------
# DATABASE
# ----------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS Departments (
    depCode   INTEGER PRIMARY KEY,
    depName   TEXT NOT NULL,
    depHead   TEXT NOT NULL,
    depTelNo  TEXT
);

CREATE TABLE IF NOT EXISTS Employees (
    empID     INTEGER PRIMARY KEY,
    depCode   INTEGER NOT NULL,
    empFName  TEXT NOT NULL,
    empLName  TEXT NOT NULL,
    empRPH    REAL NOT NULL,
    FOREIGN KEY (depCode) REFERENCES Departments(depCode)
);

CREATE TABLE IF NOT EXISTS Attendance (
    attRN      INTEGER PRIMARY KEY AUTOINCREMENT,
    empID      INTEGER NOT NULL,
    attDate    TEXT NOT NULL,          -- YYYY-MM-DD
    attTimeIn  TEXT NOT NULL,          -- YYYY-MM-DD HH:MM
    attTimeOut TEXT NOT NULL,          -- YYYY-MM-DD HH:MM
    attStat    TEXT NOT NULL DEFAULT 'Active',   -- Active / Cancelled
    FOREIGN KEY (empID) REFERENCES Employees(empID)
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    # seed sample data (same as the sample interfaces) only if empty
    if db.execute("SELECT COUNT(*) FROM Departments").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO Departments VALUES (?,?,?,?)",
            [
                (10, "Accounting", "Julius", "2557777"),
                (11, "Warehouse", "Caesar", "2551111"),
                (12, "HR", "Gretchen", "2552222"),
                (13, "IT", "Gilbert", "2553333"),
                (14, "Production", "Troy", "2554444"),
                (15, "QA", "Evangeline", "2550000"),
                (16, "Marketing", "Jessica", "2558888"),
            ],
        )
        db.executemany(
            "INSERT INTO Employees VALUES (?,?,?,?,?)",
            [
                (234, 10, "Neil", "Basabe", 500),
                (235, 10, "Heubert", "Ferolino", 300),
                (236, 11, "Denis", "Durano", 200),
                (237, 13, "Jennifer", "Amores", 500),
                (238, 15, "Catherine", "Carumba", 350),
                (239, 15, "Leah", "Ybanez", 345),
                (240, 14, "Leo", "Bermudez", 290),
            ],
        )
        for d in range(15, 21):
            db.execute(
                "INSERT INTO Attendance (empID, attDate, attTimeIn, attTimeOut, attStat) "
                "VALUES (234, ?, ?, ?, 'Active')",
                (f"2024-04-{d}", f"2024-04-{d} 08:20", f"2024-04-{d} 17:20"),
            )
    db.commit()
    db.close()


# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------
@app.context_processor
def inject_css():
    return {"use_local_css": os.path.exists(LOCAL_CSS)}


@app.template_filter("dt")
def fmt_dt(value):
    """'2024-04-15 08:20' -> '4/15/24 8:20AM'"""
    try:
        d = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return f"{d.month}/{d.day}/{d:%y} {d.hour % 12 or 12}:{d:%M}{d:%p}"
    except (ValueError, TypeError):
        return value


@app.template_filter("money")
def fmt_money(value):
    return f"{float(value):,.2f}"


def clean_dt(value):
    """datetime-local gives 'YYYY-MM-DDTHH:MM' -> 'YYYY-MM-DD HH:MM'"""
    return value.replace("T", " ")


HOURS_SQL = "ROUND((julianday(a.attTimeOut) - julianday(a.attTimeIn)) * 24, 2)"


# ----------------------------------------------------------------------
# MENU
# ----------------------------------------------------------------------
@app.route("/")
def menu():
    return render_template("menu.html")


# ----------------------------------------------------------------------
# DEPARTMENTS MANAGEMENT
# ----------------------------------------------------------------------
@app.route("/departments")
def departments():
    rows = get_db().execute("SELECT * FROM Departments ORDER BY depCode").fetchall()
    return render_template("departments.html", rows=rows)


@app.route("/departments/add", methods=["GET", "POST"])
def department_add():
    if request.method == "POST":
        try:
            get_db().execute(
                "INSERT INTO Departments VALUES (?,?,?,?)",
                (
                    int(request.form["depCode"]),
                    request.form["depName"].strip(),
                    request.form["depHead"].strip(),
                    request.form["depTelNo"].strip(),
                ),
            )
            get_db().commit()
            flash("Department added.", "ok")
            return redirect(url_for("departments"))
        except (sqlite3.IntegrityError, ValueError):
            flash("Could not add: invalid input or duplicate code.", "err")
    return render_template("dept_form.html", d=None)


@app.route("/departments/edit/<int:code>", methods=["GET", "POST"])
def department_edit(code):
    db = get_db()
    d = db.execute("SELECT * FROM Departments WHERE depCode=?", (code,)).fetchone()
    if d is None:
        return redirect(url_for("departments"))
    if request.method == "POST":
        db.execute(
            "UPDATE Departments SET depName=?, depHead=?, depTelNo=? WHERE depCode=?",
            (
                request.form["depName"].strip(),
                request.form["depHead"].strip(),
                request.form["depTelNo"].strip(),
                code,
            ),
        )
        db.commit()
        flash("Department updated.", "ok")
        return redirect(url_for("departments"))
    return render_template("dept_form.html", d=d)


@app.route("/departments/delete/<int:code>", methods=["POST"])
def department_delete(code):
    try:
        get_db().execute("DELETE FROM Departments WHERE depCode=?", (code,))
        get_db().commit()
        flash("Department deleted.", "ok")
    except sqlite3.IntegrityError:
        flash("Cannot delete: employees still belong to this department.", "err")
    return redirect(url_for("departments"))


# ----------------------------------------------------------------------
# EMPLOYEES MANAGEMENT
# ----------------------------------------------------------------------
@app.route("/employees")
def employees():
    rows = get_db().execute("SELECT * FROM Employees ORDER BY empID").fetchall()
    return render_template("employees.html", rows=rows)


@app.route("/employees/add", methods=["GET", "POST"])
def employee_add():
    db = get_db()
    deps = db.execute("SELECT * FROM Departments ORDER BY depCode").fetchall()
    if request.method == "POST":
        try:
            db.execute(
                "INSERT INTO Employees VALUES (?,?,?,?,?)",
                (
                    int(request.form["empID"]),
                    int(request.form["depCode"]),
                    request.form["empFName"].strip(),
                    request.form["empLName"].strip(),
                    float(request.form["empRPH"]),
                ),
            )
            db.commit()
            flash("Employee added.", "ok")
            return redirect(url_for("employees"))
        except (sqlite3.IntegrityError, ValueError):
            flash("Could not add: invalid input or duplicate ID.", "err")
    return render_template("emp_form.html", e=None, deps=deps)


@app.route("/employees/edit/<int:emp_id>", methods=["GET", "POST"])
def employee_edit(emp_id):
    db = get_db()
    e = db.execute("SELECT * FROM Employees WHERE empID=?", (emp_id,)).fetchone()
    if e is None:
        return redirect(url_for("employees"))
    deps = db.execute("SELECT * FROM Departments ORDER BY depCode").fetchall()
    if request.method == "POST":
        db.execute(
            "UPDATE Employees SET depCode=?, empFName=?, empLName=?, empRPH=? WHERE empID=?",
            (
                int(request.form["depCode"]),
                request.form["empFName"].strip(),
                request.form["empLName"].strip(),
                float(request.form["empRPH"]),
                emp_id,
            ),
        )
        db.commit()
        flash("Employee updated.", "ok")
        return redirect(url_for("employees"))
    return render_template("emp_form.html", e=e, deps=deps)


@app.route("/employees/delete/<int:emp_id>", methods=["POST"])
def employee_delete(emp_id):
    try:
        get_db().execute("DELETE FROM Employees WHERE empID=?", (emp_id,))
        get_db().commit()
        flash("Employee deleted.", "ok")
    except sqlite3.IntegrityError:
        flash("Cannot delete: employee has attendance records.", "err")
    return redirect(url_for("employees"))


# ----------------------------------------------------------------------
# ATTENDANCE RECORDING
# ----------------------------------------------------------------------
@app.route("/attendance")
def attendance():
    rows = get_db().execute("SELECT * FROM Attendance ORDER BY attRN").fetchall()
    return render_template("attendance.html", rows=rows)


@app.route("/attendance/add", methods=["GET", "POST"])
def attendance_add():
    db = get_db()
    emps = db.execute("SELECT * FROM Employees ORDER BY empID").fetchall()
    if request.method == "POST":
        t_in = clean_dt(request.form["attTimeIn"])
        t_out = clean_dt(request.form["attTimeOut"])
        if t_out <= t_in:
            flash("Time Out must be later than Time In.", "err")
        else:
            try:
                db.execute(
                    "INSERT INTO Attendance (empID, attDate, attTimeIn, attTimeOut, attStat) "
                    "VALUES (?,?,?,?, 'Active')",
                    (int(request.form["empID"]), t_in[:10], t_in, t_out),
                )
                db.commit()
                flash("Attendance recorded.", "ok")
                return redirect(url_for("attendance"))
            except (sqlite3.IntegrityError, ValueError):
                flash("Invalid employee.", "err")
    return render_template("att_form.html", emps=emps)


@app.route("/attendance/cancel/<int:rn>", methods=["POST"])
def attendance_cancel(rn):
    db = get_db()
    db.execute("UPDATE Attendance SET attStat='Cancelled' WHERE attRN=?", (rn,))
    db.commit()
    flash(f"Record #{rn} cancelled.", "ok")
    return redirect(url_for("attendance"))


# ----------------------------------------------------------------------
# ATTENDANCE MONITORING (BY EMPLOYEE)
# ----------------------------------------------------------------------
@app.route("/monitor/employee")
def monitor_employee():
    emp_id = request.args.get("emp", "").strip()
    emp, rows, total = None, [], 0
    if emp_id:
        db = get_db()
        emp = db.execute(
            "SELECT e.*, d.depName FROM Employees e "
            "JOIN Departments d ON d.depCode = e.depCode WHERE e.empID=?",
            (emp_id,),
        ).fetchone()
        if emp is None:
            flash("Employee not found.", "err")
        else:
            rows = db.execute(
                f"SELECT a.*, {HOURS_SQL} AS hours FROM Attendance a "
                "WHERE a.empID=? AND a.attStat != 'Cancelled' ORDER BY a.attRN",
                (emp_id,),
            ).fetchall()
            total = sum(r["hours"] for r in rows)
    return render_template(
        "mon_emp.html", emp=emp, rows=rows, total=total, emp_id=emp_id,
        today=datetime.now().strftime("%m/%d/%Y"),
    )


# ----------------------------------------------------------------------
# ATTENDANCE MONITORING (DATE RANGE)
# ----------------------------------------------------------------------
@app.route("/monitor/range")
def monitor_range():
    d_from = request.args.get("date_from", "")
    d_to = request.args.get("date_to", "")
    rows, total = [], 0
    if d_from and d_to:
        rows = get_db().execute(
            f"SELECT a.*, {HOURS_SQL} AS hours FROM Attendance a "
            "WHERE a.attDate BETWEEN ? AND ? AND a.attStat != 'Cancelled' "
            "ORDER BY a.attRN",
            (d_from, d_to),
        ).fetchall()
        total = sum(r["hours"] for r in rows)
    return render_template(
        "mon_range.html", rows=rows, total=total, d_from=d_from, d_to=d_to,
        searched=bool(d_from and d_to), today=datetime.now().strftime("%m/%d/%Y"),
    )


# ----------------------------------------------------------------------
# TEMPLATES (inline so the whole project is a single file)
# ----------------------------------------------------------------------
TEMPLATES = {
    "base.html": """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Employee Attendance System</title>
{% if use_local_css %}
<link href="{{ url_for('static', filename='bootstrap.min.css') }}" rel="stylesheet">
{% else %}
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
{% endif %}
</head>
<body>
<nav class="navbar navbar-dark bg-dark mb-4">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('menu') }}">Employee Attendance System</a>
  </div>
</nav>
<div class="container pb-5">
{% with msgs = get_flashed_messages(with_categories=true) %}
  {% for cat, m in msgs %}
  <div class="alert alert-{{ 'success' if cat == 'ok' else 'danger' }}">{{ m }}</div>
  {% endfor %}
{% endwith %}
{% block content %}{% endblock %}
</div>
</body></html>""",

    "menu.html": """{% extends 'base.html' %}{% block content %}
<h3>Employee Attendance Monitoring System</h3>
<p class="fw-bold">Choose your Transaction:</p>
<div class="list-group col-md-6">
 <a class="list-group-item list-group-item-action" href="{{ url_for('departments') }}">Departments Management</a>
 <a class="list-group-item list-group-item-action" href="{{ url_for('employees') }}">Employees Management</a>
 <a class="list-group-item list-group-item-action" href="{{ url_for('attendance') }}">Attendance Recording</a>
 <a class="list-group-item list-group-item-action" href="{{ url_for('monitor_employee') }}">Attendance Monitoring (By Employee)</a>
 <a class="list-group-item list-group-item-action" href="{{ url_for('monitor_range') }}">Attendance Monitoring (Date Range)</a>
</div>
{% endblock %}""",

    "departments.html": """{% extends 'base.html' %}{% block content %}
<h3>Departments Management</h3>
<div class="mb-3">
 <a class="btn btn-primary" href="{{ url_for('department_add') }}">Add a Department Here</a>
 <a class="btn btn-secondary" href="{{ url_for('menu') }}">Back to Menu</a>
</div>
<table class="table table-bordered table-striped text-center align-middle">
<thead class="table-dark"><tr><th>Code</th><th>Name</th><th>Head</th><th>Tel. No.</th><th>Actions</th></tr></thead>
{% for r in rows %}
<tr><td>{{ r.depCode }}</td><td>{{ r.depName }}</td><td>{{ r.depHead }}</td><td>{{ r.depTelNo }}</td>
<td>
 <a class="btn btn-sm btn-warning" href="{{ url_for('department_edit', code=r.depCode) }}">Edit</a>
 <form class="d-inline" method="post" action="{{ url_for('department_delete', code=r.depCode) }}"
  onsubmit="return confirm('Delete this department?')"><button class="btn btn-sm btn-danger">Del</button></form>
</td></tr>
{% endfor %}
</table>{% endblock %}""",

    "dept_form.html": """{% extends 'base.html' %}{% block content %}
<h3>{{ 'Edit' if d else 'Add' }} Department</h3>
<form method="post" class="col-md-5">
 <div class="mb-3"><label class="form-label">Code</label>
  <input class="form-control" name="depCode" type="number" required value="{{ d.depCode if d }}" {{ 'readonly' if d }}></div>
 <div class="mb-3"><label class="form-label">Name</label>
  <input class="form-control" name="depName" required value="{{ d.depName if d }}"></div>
 <div class="mb-3"><label class="form-label">Head</label>
  <input class="form-control" name="depHead" required value="{{ d.depHead if d }}"></div>
 <div class="mb-3"><label class="form-label">Tel. No.</label>
  <input class="form-control" name="depTelNo" value="{{ d.depTelNo if d }}"></div>
 <button class="btn btn-success">Save</button>
 <a class="btn btn-secondary" href="{{ url_for('departments') }}">Cancel</a>
</form>{% endblock %}""",

    "employees.html": """{% extends 'base.html' %}{% block content %}
<h3>Employees Management</h3>
<div class="mb-3">
 <a class="btn btn-primary" href="{{ url_for('employee_add') }}">Add an Employee Here</a>
 <a class="btn btn-secondary" href="{{ url_for('menu') }}">Back to Menu</a>
</div>
<table class="table table-bordered table-striped text-center align-middle">
<thead class="table-dark"><tr><th>ID</th><th>Dept.</th><th>Lastname</th><th>Firstname</th><th>Rate/Hour</th><th>Actions</th></tr></thead>
{% for r in rows %}
<tr><td>{{ r.empID }}</td><td>{{ r.depCode }}</td><td>{{ r.empLName }}</td><td>{{ r.empFName }}</td>
<td>{{ r.empRPH | money }}</td>
<td>
 <a class="btn btn-sm btn-warning" href="{{ url_for('employee_edit', emp_id=r.empID) }}">Edit</a>
 <form class="d-inline" method="post" action="{{ url_for('employee_delete', emp_id=r.empID) }}"
  onsubmit="return confirm('Delete this employee?')"><button class="btn btn-sm btn-danger">Del</button></form>
</td></tr>
{% endfor %}
</table>{% endblock %}""",

    "emp_form.html": """{% extends 'base.html' %}{% block content %}
<h3>{{ 'Edit' if e else 'Add' }} Employee</h3>
<form method="post" class="col-md-5">
 <div class="mb-3"><label class="form-label">ID</label>
  <input class="form-control" name="empID" type="number" required value="{{ e.empID if e }}" {{ 'readonly' if e }}></div>
 <div class="mb-3"><label class="form-label">Department</label>
  <select class="form-select" name="depCode" required>
   {% for d in deps %}<option value="{{ d.depCode }}" {{ 'selected' if e and e.depCode == d.depCode }}>
     {{ d.depCode }} - {{ d.depName }}</option>{% endfor %}
  </select></div>
 <div class="mb-3"><label class="form-label">Lastname</label>
  <input class="form-control" name="empLName" required value="{{ e.empLName if e }}"></div>
 <div class="mb-3"><label class="form-label">Firstname</label>
  <input class="form-control" name="empFName" required value="{{ e.empFName if e }}"></div>
 <div class="mb-3"><label class="form-label">Rate/Hour</label>
  <input class="form-control" name="empRPH" type="number" step="0.01" min="0" required value="{{ e.empRPH if e }}"></div>
 <button class="btn btn-success">Save</button>
 <a class="btn btn-secondary" href="{{ url_for('employees') }}">Cancel</a>
</form>{% endblock %}""",

    "attendance.html": """{% extends 'base.html' %}{% block content %}
<h3>Attendance Recording</h3>
<div class="mb-3">
 <a class="btn btn-primary" href="{{ url_for('attendance_add') }}">Record Attendance Here</a>
 <a class="btn btn-secondary" href="{{ url_for('menu') }}">Back to Menu</a>
</div>
<table class="table table-bordered table-striped text-center align-middle">
<thead class="table-dark"><tr><th>Record #</th><th>Emp. ID</th><th>Date/Time In</th><th>Date/Time Out</th><th>Status</th><th>Action</th></tr></thead>
{% for r in rows %}
<tr {% if r.attStat == 'Cancelled' %}class="text-muted"{% endif %}>
<td>{{ r.attRN }}</td><td>{{ r.empID }}</td><td>{{ r.attTimeIn | dt }}</td><td>{{ r.attTimeOut | dt }}</td>
<td>{{ r.attStat }}</td>
<td>{% if r.attStat != 'Cancelled' %}
 <form class="d-inline" method="post" action="{{ url_for('attendance_cancel', rn=r.attRN) }}"
  onsubmit="return confirm('Cancel this record?')"><button class="btn btn-sm btn-danger">Cancel</button></form>
 {% else %}-{% endif %}</td></tr>
{% endfor %}
</table>{% endblock %}""",

    "att_form.html": """{% extends 'base.html' %}{% block content %}
<h3>Record Attendance</h3>
<form method="post" class="col-md-5">
 <div class="mb-3"><label class="form-label">Employee</label>
  <select class="form-select" name="empID" required>
   {% for e in emps %}<option value="{{ e.empID }}">{{ e.empID }} - {{ e.empLName }}, {{ e.empFName }}</option>{% endfor %}
  </select></div>
 <div class="mb-3"><label class="form-label">Date/Time In</label>
  <input class="form-control" type="datetime-local" name="attTimeIn" required></div>
 <div class="mb-3"><label class="form-label">Date/Time Out</label>
  <input class="form-control" type="datetime-local" name="attTimeOut" required></div>
 <button class="btn btn-success">Save</button>
 <a class="btn btn-secondary" href="{{ url_for('attendance') }}">Cancel</a>
</form>{% endblock %}""",

    "mon_emp.html": """{% extends 'base.html' %}{% block content %}
<h3>Attendance Monitoring (By Employee)</h3>
<div class="d-flex justify-content-between mb-3">
 <form method="get" class="d-flex gap-2 align-items-center">
  <label class="form-label mb-0">Input Employee #:</label>
  <input class="form-control w-auto" name="emp" type="number" value="{{ emp_id }}" required>
  <button class="btn btn-primary">Search</button>
 </form>
 <a class="btn btn-secondary" href="{{ url_for('menu') }}">Back to Menu</a>
</div>
{% if emp %}
<div class="d-flex justify-content-between">
 <span><b>Name:</b> {{ emp.empLName }}, {{ emp.empFName }}</span>
 <span><b>Department:</b> {{ emp.depName }}</span>
</div>
<table class="table table-bordered table-striped text-center mt-3">
<thead class="table-dark"><tr><th>Record #</th><th>Emp. ID</th><th>Date/Time In</th><th>Date/Time Out</th><th>Total</th></tr></thead>
{% for r in rows %}
<tr><td>{{ loop.index }}</td><td>{{ r.empID }}</td><td>{{ r.attTimeIn | dt }}</td>
<td>{{ r.attTimeOut | dt }}</td><td>{{ '%.2f' % r.hours }}</td></tr>
{% else %}<tr><td colspan="5">No attendance records.</td></tr>{% endfor %}
</table>
<div class="d-flex justify-content-between">
 <div><b>Rate Per Hour:</b> {{ emp.empRPH | money }}<br>
  <b>Salary:</b> P{{ (emp.empRPH * total) | money }}</div>
 <div class="text-end"><b>Total Hours Worked:</b> {{ '%.2f' % total }}<br><b>Date Generated:</b> {{ today }}</div>
</div>
{% endif %}{% endblock %}""",

    "mon_range.html": """{% extends 'base.html' %}{% block content %}
<h3>Attendance Monitoring (Date Range)</h3>
<div class="text-end mb-3"><a class="btn btn-secondary" href="{{ url_for('menu') }}">Back to Menu</a></div>
<form method="get" class="d-flex gap-3 align-items-center mb-3">
 <label class="form-label mb-0">Date From:</label>
 <input class="form-control w-auto" type="date" name="date_from" value="{{ d_from }}" required>
 <label class="form-label mb-0">Date To:</label>
 <input class="form-control w-auto" type="date" name="date_to" value="{{ d_to }}" required>
 <button class="btn btn-primary">Generate</button>
</form>
{% if searched %}
<h5>Attendance Records...</h5>
<table class="table table-bordered table-striped text-center">
<thead class="table-dark"><tr><th>Record #</th><th>Emp. ID</th><th>Date/Time In</th><th>Date/Time Out</th><th>Total</th></tr></thead>
{% for r in rows %}
<tr><td>{{ loop.index }}</td><td>{{ r.empID }}</td><td>{{ r.attTimeIn | dt }}</td>
<td>{{ r.attTimeOut | dt }}</td><td>{{ '%.2f' % r.hours }}</td></tr>
{% else %}<tr><td colspan="5">No attendance records in this range.</td></tr>{% endfor %}
</table>
<div class="d-flex justify-content-between">
 <div><b>Date Generated:</b> {{ today }}</div>
 <div><b>Total:</b> {{ '%.2f' % total }}</div>
</div>
{% endif %}{% endblock %}""",
}
app.jinja_loader = DictLoader(TEMPLATES)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)