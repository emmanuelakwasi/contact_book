from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import csv, os, uuid, io
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.csv")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.csv")

def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["username","password_hash","created_at"])
            writer.writeheader()
    if not os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id","owner","name","phone","email","created_at"])
            writer.writeheader()

ensure_files()

app = Flask(__name__)
import os
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")



def current_user():
    return session.get("user")

def get_user_contacts(username):
    ensure_files()
    contacts = []
    with open(CONTACTS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["owner"] == username:
                contacts.append(row)
    
    contacts.sort(key=lambda r: r["name"].lower())
    return contacts

def write_all_contacts(rows):
    with open(CONTACTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","owner","name","phone","email","created_at"])
        writer.writeheader()
        writer.writerows(rows)

def read_all_contacts():
    with open(CONTACTS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

def valid_phone(phone):
    pattern = r"^\+?\d{7,15}$"
    return re.match(pattern, phone)




@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        if not username or not password:
            flash("Username and password required.", "error")
            return redirect(url_for("signup"))
        
        with open(USERS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["username"] == username:
                    flash("Username already exists.", "error")
                    return redirect(url_for("signup"))
        
        with open(USERS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["username","password_hash","created_at"])
            writer.writerow({
                "username": username,
                "password_hash": generate_password_hash(password),
                "created_at": datetime.utcnow().isoformat()
            })
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        user = None
        with open(USERS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["username"] == username:
                    user = row
                    break
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("login"))
        session["user"] = username
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    q = request.args.get("q","").strip().lower()
    contacts = get_user_contacts(user)
    if q:
        contacts = [c for c in contacts if q in json.dumps(c).lower()]
    return render_template("dashboard.html", contacts=contacts, query=q)

@app.route("/add", methods=["POST"])
def add_contact():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    email = request.form.get("email","").strip()
    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("dashboard"))
    if email and not valid_email(email):
        flash("Invalid email format.", "error")
        return redirect(url_for("dashboard"))
    if phone and not valid_phone(phone):
        flash("Invalid phone number format.", "error")
        return redirect(url_for("dashboard"))

    
    existing = get_user_contacts(user)
    if any((c["name"].lower()==name.lower() and c["phone"]==phone) or (email and c["email"].lower()==email.lower()) for c in existing):
        flash("Duplicate contact detected.", "error")
        return redirect(url_for("dashboard"))
    row = {
        "id": str(uuid.uuid4()),
        "owner": user,
        "name": name,
        "phone": phone,
        "email": email,
        "created_at": datetime.utcnow().isoformat()
    }
    all_rows = read_all_contacts()
    all_rows.append(row)
    write_all_contacts(all_rows)
    flash("Contact added.", "success")
    return redirect(url_for("dashboard"))

@app.route("/edit/<id>", methods=["POST"])
def edit_contact(id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    email = request.form.get("email","").strip()
    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("dashboard"))
    if email and not valid_email(email):
        flash("Invalid email format.", "error")
        return redirect(url_for("dashboard"))
    rows = read_all_contacts()
    updated = False
    for r in rows:
        if r["id"] == id and r["owner"] == user:
            r["name"] = name
            r["phone"] = phone
            r["email"] = email
            updated = True
            break
    write_all_contacts(rows)
    if updated:
        flash("Contact updated.", "success")
    else:
        flash("Contact not found.", "error")
    return redirect(url_for("dashboard"))

@app.route("/delete/<id>", methods=["POST"])
def delete_contact(id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    rows = read_all_contacts()
    new_rows = [r for r in rows if not (r["id"]==id and r["owner"]==user)]
    write_all_contacts(new_rows)
    flash("Contact deleted.", "success")
    return redirect(url_for("dashboard"))


from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def generate_all_contacts_pdf(username):
    contacts = get_user_contacts(username)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    margin = 0.75 * inch
    y = height - margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, f"Contacts for {username}")
    y -= 0.35*inch
    c.setFont("Helvetica", 11)
    if not contacts:
        c.drawString(margin, y, "No contacts found.")
    else:
        
        c.drawString(margin, y, "Name")
        c.drawString(margin + 2.8*inch, y, "Phone")
        c.drawString(margin + 4.2*inch, y, "Email")
        y -= 0.2*inch
        c.line(margin, y, width - margin, y)
        y -= 0.15*inch
        for ct in contacts:
            if y < margin:
                c.showPage()
                y = height - margin
            c.drawString(margin, y, ct.get("name",""))
            c.drawString(margin + 2.8*inch, y, ct.get("phone",""))
            c.drawString(margin + 4.2*inch, y, ct.get("email",""))
            y -= 0.22*inch
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_single_contact_pdf(username, contact_id):
    contacts = get_user_contacts(username)
    ct = next((c for c in contacts if c["id"]==contact_id), None)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    margin = 1*inch
    y = 10*inch
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Contact Details")
    y -= 0.4*inch
    c.setFont("Helvetica", 12)
    if not ct:
        c.drawString(margin, y, "Contact not found.")
    else:
        fields = [
            ("Name", ct.get("name","")),
            ("Phone", ct.get("phone","")),
            ("Email", ct.get("email","")),
            ("Created At", ct.get("created_at",""))
        ]
        for label, val in fields:
            c.drawString(margin, y, f"{label}: {val}")
            y -= 0.3*inch
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

@app.route("/export/all.pdf")
def export_all():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    pdf = generate_all_contacts_pdf(user)
    return send_file(pdf, as_attachment=True, download_name=f"{user}_contacts.pdf", mimetype="application/pdf")

@app.route("/export/<id>.pdf")
def export_one(id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    pdf = generate_single_contact_pdf(user, id)
    return send_file(pdf, as_attachment=True, download_name=f"contact_{id}.pdf", mimetype="application/pdf")


@app.route("/theme", methods=["POST"])
def toggle_theme():
    current = session.get("theme","light")
    session["theme"] = "dark" if current == "light" else "light"
    return ("", 204)

if __name__ == "__main__":
    app.run(debug=True)
