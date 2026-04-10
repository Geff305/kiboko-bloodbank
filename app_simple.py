import hashlib
import json
import time
import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ==================== SIMULATED BLOCKCHAIN ====================
class Block:
    def __init__(self, index, transactions, timestamp, previous_hash):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.hash = self.compute_hash()
    
    def compute_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = []
        self.load_from_file()
        if not self.chain:
            self.create_genesis_block()
    
    def create_genesis_block(self):
        genesis_block = Block(0, ["Genesis Block"], time.time(), "0")
        self.chain.append(genesis_block)
        self.save_to_file()
    
    def add_block(self, transaction):
        last_block = self.chain[-1]
        new_block = Block(len(self.chain), [transaction], time.time(), last_block.hash)
        self.chain.append(new_block)
        self.save_to_file()
        return new_block.hash
    
    def save_to_file(self):
        data = [{"index": b.index, "transactions": b.transactions, "timestamp": b.timestamp, "previous_hash": b.previous_hash, "hash": b.hash} for b in self.chain]
        with open("blockchain.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def load_from_file(self):
        try:
            with open("blockchain.json", "r") as f:
                data = json.load(f)
                for item in data:
                    block = Block(item["index"], item["transactions"], item["timestamp"], item["previous_hash"])
                    block.hash = item["hash"]
                    self.chain.append(block)
        except FileNotFoundError:
            pass
    
    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            if self.chain[i].hash != self.chain[i].compute_hash() or self.chain[i].previous_hash != self.chain[i-1].hash:
                return False
        return True

blockchain = Blockchain()

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('bloodbank_professional.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        is_approved INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS donors (
        user_id INTEGER PRIMARY KEY,
        blood_type TEXT,
        medical_history TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS hospitals (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        location TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS blood_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_user_id INTEGER,
        blood_type TEXT,
        quantity INTEGER,
        urgency TEXT,
        status TEXT,
        admin_approved INTEGER DEFAULT 0,
        tx_hash TEXT,
        request_date TIMESTAMP,
        fulfilled_by_donor_id INTEGER,
        remaining_quantity INTEGER,
        FOREIGN KEY (hospital_user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        blood_type TEXT PRIMARY KEY,
        quantity INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS donation_tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_user_id INTEGER,
        request_id INTEGER,
        blood_type TEXT,
        quantity INTEGER,
        tx_hash TEXT,
        timestamp TIMESTAMP
    )''')
    # Initialize inventory
    for bt in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
        c.execute("INSERT OR IGNORE INTO inventory (blood_type, quantity) VALUES (?, 0)", (bt,))
    # Admin user (password: admin123)
    c.execute("INSERT OR IGNORE INTO users (id, username, password, role, full_name, is_approved) VALUES (1, 'admin', 'admin123', 'admin', 'System Admin', 1)")
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('bloodbank_professional.db')

# Helper to render with Bootstrap and blockchain link on every page
BASE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blockchain Blood Bank System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f8f9fa; }
        .navbar { box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card { border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.05); }
        .table-responsive { overflow-x: auto; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">🏥 Blockchain Blood Bank</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {% if session.user_id %}
                        <li class="nav-item"><span class="nav-link text-white">Welcome, {{ session.username }} ({{ session.role }})</span></li>
                        <li class="nav-item"><a class="nav-link" href="/view_blockchain">🔗 View Blockchain</a></li>
                        <li class="nav-item"><a class="nav-link" href="/logout">Logout</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="/login">Login</a></li>
                        <li class="nav-item"><a class="nav-link" href="/register_donor">Register as Donor</a></li>
                        <li class="nav-item"><a class="nav-link" href="/register_hospital">Register Hospital</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category if category != 'message' else 'info' }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endwith %}
        {{ CONTENT|safe }}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

def render(content):
    return render_template_string(BASE_HTML, CONTENT=content, session=session)

# --------------------------- PUBLIC ROUTES ---------------------------
@app.route('/')
def index():
    content = '''
    <div class="text-center py-5">
        <h1 class="display-4">Blockchain Based Blood Bank System</h1>
        <p class="lead">Secure, transparent, and immutable blood supply chain management.</p>
        <p>Blockchain Status: <span class="badge bg-success">Valid</span></p>
        <a href="/view_blockchain" class="btn btn-outline-primary">View Blockchain</a>
        <a href="/login" class="btn btn-primary">Get Started</a>
    </div>
    '''
    return render(content)

@app.route('/register_donor', methods=['GET', 'POST'])
def register_donor():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        blood_type = request.form['blood_type']
        medical_history = request.form.get('medical_history', '')
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role, full_name, email, phone, is_approved) VALUES (?, ?, 'donor', ?, ?, ?, 1)",
                      (username, password, full_name, email, phone))
            user_id = c.lastrowid
            c.execute("INSERT INTO donors (user_id, blood_type, medical_history) VALUES (?, ?, ?)",
                      (user_id, blood_type, medical_history))
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-primary text-white">Donor Registration</div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="Username" required></div>
                        <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Password" required></div>
                        <div class="mb-3"><input type="text" name="full_name" class="form-control" placeholder="Full Name"></div>
                        <div class="mb-3"><input type="email" name="email" class="form-control" placeholder="Email"></div>
                        <div class="mb-3"><input type="text" name="phone" class="form-control" placeholder="Phone"></div>
                        <div class="mb-3"><select name="blood_type" class="form-select" required>
                            <option value="">Select Blood Type</option>
                            <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
                            <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option>
                        </select></div>
                        <div class="mb-3"><textarea name="medical_history" class="form-control" placeholder="Medical history"></textarea></div>
                        <button type="submit" class="btn btn-primary w-100">Register</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    '''
    return render(content)

@app.route('/register_hospital', methods=['GET', 'POST'])
def register_hospital():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        location = request.form['location']
        email = request.form['email']
        phone = request.form['phone']
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role, full_name, email, phone, is_approved) VALUES (?, ?, 'hospital', ?, ?, ?, 0)",
                      (username, password, name, email, phone))
            user_id = c.lastrowid
            c.execute("INSERT INTO hospitals (user_id, name, location, contact_email, contact_phone) VALUES (?, ?, ?, ?, ?)",
                      (user_id, name, location, email, phone))
            conn.commit()
            flash('Hospital registration submitted. Awaiting admin approval.', 'info')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-warning text-dark">Hospital Registration (Pending Admin Approval)</div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="Username" required></div>
                        <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Password" required></div>
                        <div class="mb-3"><input type="text" name="name" class="form-control" placeholder="Hospital Name" required></div>
                        <div class="mb-3"><input type="text" name="location" class="form-control" placeholder="Location"></div>
                        <div class="mb-3"><input type="email" name="email" class="form-control" placeholder="Email"></div>
                        <div class="mb-3"><input type="text" name="phone" class="form-control" placeholder="Phone"></div>
                        <button type="submit" class="btn btn-warning w-100">Register Hospital</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    '''
    return render(content)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password, role, is_approved FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            if user[4] == 0 and user[3] == 'hospital':
                flash('Your hospital account is pending admin approval.', 'warning')
                return redirect(url_for('login'))
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            if user[3] == 'donor':
                return redirect(url_for('donor_dashboard'))
            elif user[3] == 'hospital':
                return redirect(url_for('hospital_dashboard'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-4">
            <div class="card">
                <div class="card-header bg-primary text-white">Login</div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="Username" required></div>
                        <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Password" required></div>
                        <button type="submit" class="btn btn-primary w-100">Login</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    '''
    return render(content)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

# --------------------------- DONOR DASHBOARD (with quantity input) ---------------------------
@app.route('/donor_dashboard')
def donor_dashboard():
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT blood_type FROM donors WHERE user_id = ?", (user_id,))
    donor_bt = c.fetchone()[0]
    # Show approved blood requests matching donor's blood type, with remaining_quantity > 0, and not fully fulfilled
    c.execute('''SELECT br.id, u.full_name as hospital_name, br.blood_type, br.remaining_quantity, br.quantity, br.urgency, br.request_date 
                 FROM blood_requests br 
                 JOIN users u ON br.hospital_user_id = u.id 
                 WHERE br.admin_approved = 1 AND br.status != 'fulfilled' AND br.blood_type = ? AND br.remaining_quantity > 0
                 ORDER BY br.request_date ASC''', (donor_bt,))
    requests = c.fetchall()
    # Show donor's donation history
    c.execute("SELECT * FROM donation_tx WHERE donor_user_id = ? ORDER BY timestamp DESC", (user_id,))
    donations = c.fetchall()
    conn.close()
    req_rows = ''
    for r in requests:
        req_rows += f'''
        <form method="post" action="/donate_to_request/{r[0]}" class="mb-3">
            <tr>
                <td>{r[1]}</td><td>{r[2]}</td>
                <td>Requested: {r[4]} units<br>Remaining: {r[3]} units</td>
                <td>{r[5]}</td><td>{r[6]}</td>
                <td><input type="number" name="donate_units" class="form-control form-control-sm" placeholder="Units to donate" min="1" max="{r[3]}" required style="width:120px;"></td>
                <td><button type="submit" class="btn btn-sm btn-success">Donate</button></td>
            </tr>
        </form>
        '''
    don_rows = ''
    for d in donations:
        don_rows += f'<tr><td>{d[3]}</td><td>{d[4]} units</td><td>{d[5][:10]}...</td><td>{d[6]}</td></tr>'
    content = f'''
    <div class="row">
        <div class="col-md-12">
            <div class="card mb-4">
                <div class="card-header bg-success text-white">Your Blood Type: {donor_bt}</div>
                <div class="card-body">
                    <h5>Available Blood Requests (Matching Your Type)</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead><tr><th>Hospital</th><th>Blood Type</th><th>Quantity</th><th>Urgency</th><th>Date</th><th>Donate Units</th><th>Action</th></tr></thead>
                            <tbody>{req_rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Your Donation History</div>
                <div class="card-body">
                    <table class="table">
                        <thead><tr><th>Blood Type</th><th>Quantity</th><th>Tx Hash</th><th>Date</th></tr></thead>
                        <tbody>{don_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    '''
    return render(content)

@app.route('/donate_to_request/<int:request_id>', methods=['POST'])
def donate_to_request(request_id):
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    donor_id = session['user_id']
    donate_units = int(request.form['donate_units'])
    conn = get_db()
    c = conn.cursor()
    # Verify request exists, is approved, has remaining quantity, and matches donor's blood type
    c.execute("SELECT blood_type, remaining_quantity, hospital_user_id FROM blood_requests WHERE id = ? AND admin_approved = 1 AND status != 'fulfilled'", (request_id,))
    req = c.fetchone()
    if not req:
        flash('Request not available or already fulfilled.', 'danger')
        return redirect(url_for('donor_dashboard'))
    blood_type, remaining, hospital_id = req
    if donate_units <= 0 or donate_units > remaining:
        flash(f'Invalid quantity. Maximum you can donate is {remaining} units.', 'danger')
        return redirect(url_for('donor_dashboard'))
    c.execute("SELECT blood_type FROM donors WHERE user_id = ?", (donor_id,))
    donor_bt = c.fetchone()[0]
    if donor_bt != blood_type:
        flash('Your blood type does not match this request.', 'danger')
        return redirect(url_for('donor_dashboard'))
    
    # Record donation on blockchain
    transaction = f"Donation: {donate_units} units of {blood_type} by Donor {donor_id} to Hospital {hospital_id} for Request {request_id}"
    tx_hash = blockchain.add_block(transaction)
    
    # Update inventory
    c.execute("UPDATE inventory SET quantity = quantity + ? WHERE blood_type = ?", (donate_units, blood_type))
    
    # Update request: reduce remaining quantity; if zero, mark as fulfilled
    new_remaining = remaining - donate_units
    if new_remaining == 0:
        c.execute("UPDATE blood_requests SET remaining_quantity = 0, status = 'fulfilled', fulfilled_by_donor_id = ? WHERE id = ?", (donor_id, request_id))
    else:
        c.execute("UPDATE blood_requests SET remaining_quantity = ? WHERE id = ?", (new_remaining, request_id))
    
    # Record donation transaction
    c.execute("INSERT INTO donation_tx (donor_user_id, request_id, blood_type, quantity, tx_hash) VALUES (?, ?, ?, ?, ?)",
              (donor_id, request_id, blood_type, donate_units, tx_hash))
    conn.commit()
    conn.close()
    flash(f'Donation of {donate_units} units recorded! Request #{request_id} updated. Tx: {tx_hash[:20]}...', 'success')
    return redirect(url_for('donor_dashboard'))

# --------------------------- HOSPITAL DASHBOARD (with remaining_quantity) ---------------------------
@app.route('/hospital_dashboard')
def hospital_dashboard():
    if session.get('role') != 'hospital':
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_approved FROM users WHERE id = ?", (user_id,))
    approved = c.fetchone()[0]
    if not approved:
        conn.close()
        flash('Your hospital account is still pending admin approval.', 'warning')
        return redirect(url_for('login'))
    c.execute("SELECT * FROM blood_requests WHERE hospital_user_id = ? ORDER BY request_date DESC", (user_id,))
    requests = c.fetchall()
    c.execute("SELECT * FROM inventory")
    inventory = c.fetchall()
    conn.close()
    req_rows = ''
    for r in requests:
        req_rows += f'''
        <tr>
            <td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td>
            <td>{r[5]}</td><td>{"Approved" if r[6] else "Pending"}</td>
            <td>{r[7][:10] if r[7] else "N/A"}...</td>
            <td>{r[10] if r[10] is not None else r[3]}</td>
            <td>{r[5]}</td>
        </tr>
        '''
    inv_rows = ''.join(f'<tr><td>{i[0]}</td><td>{i[1]}</td></tr>' for i in inventory)
    content = f'''
    <div class="row">
        <div class="col-md-12">
            <div class="card mb-4">
                <div class="card-header bg-info text-white">Create New Blood Request</div>
                <div class="card-body">
                    <form method="post" action="/create_request" class="row g-3">
                        <div class="col-auto"><select name="blood_type" class="form-select" required><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select></div>
                        <div class="col-auto"><input type="number" name="quantity" class="form-control" placeholder="Quantity (units)" required></div>
                        <div class="col-auto"><select name="urgency" class="form-select"><option>Routine</option><option>Urgent</option><option>Emergency</option></select></div>
                        <div class="col-auto"><button type="submit" class="btn btn-primary">Submit Request (Pending Admin Approval)</button></div>
                    </form>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-header">Your Blood Requests</div>
                <div class="card-body">
                    <table class="table">
                        <thead><tr><th>Blood Type</th><th>Quantity</th><th>Urgency</th><th>Status</th><th>Admin Approved</th><th>Tx Hash</th><th>Remaining</th><th>Fulfilled</th></tr></thead>
                        <tbody>{req_rows}</tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Current Inventory (Blockchain)</div>
                <div class="card-body">
                    <table class="table"><thead><tr><th>Blood Type</th><th>Units Available</th></tr></thead><tbody>{inv_rows}</tbody></table>
                </div>
            </div>
        </div>
    </div>
    '''
    return render(content)

@app.route('/create_request', methods=['POST'])
def create_request():
    if session.get('role') != 'hospital':
        return redirect(url_for('login'))
    user_id = session['user_id']
    blood_type = request.form['blood_type']
    quantity = int(request.form['quantity'])
    urgency = request.form['urgency']
    conn = get_db()
    c = conn.cursor()
    transaction = f"Blood Request: {blood_type} {quantity} units from Hospital {user_id} Urgency:{urgency}"
    tx_hash = blockchain.add_block(transaction)
    c.execute("INSERT INTO blood_requests (hospital_user_id, blood_type, quantity, urgency, status, admin_approved, tx_hash, request_date, remaining_quantity) VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, ?)",
              (user_id, blood_type, quantity, urgency, tx_hash, datetime.now(), quantity))
    conn.commit()
    conn.close()
    flash('Blood request submitted. Awaiting admin approval.', 'info')
    return redirect(url_for('hospital_dashboard'))

# --------------------------- ADMIN DASHBOARD (full history) ---------------------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    # Pending hospital registrations
    c.execute("SELECT u.id, u.username, h.name, h.location, h.contact_email, h.contact_phone FROM users u JOIN hospitals h ON u.id = h.user_id WHERE u.is_approved = 0")
    pending_hospitals = c.fetchall()
    # Pending blood requests
    c.execute("SELECT br.id, u.full_name, br.blood_type, br.quantity, br.urgency, br.request_date FROM blood_requests br JOIN users u ON br.hospital_user_id = u.id WHERE br.admin_approved = 0 AND br.status = 'pending'")
    pending_requests = c.fetchall()
    # All approved hospitals
    c.execute("SELECT u.id, u.full_name, h.location FROM users u JOIN hospitals h ON u.id = h.user_id WHERE u.is_approved = 1")
    approved_hospitals = c.fetchall()
    # Full history: all donations
    c.execute('''SELECT d.id, u.username as donor, d.blood_type, d.quantity, d.tx_hash, d.timestamp, br.id as request_id 
                 FROM donation_tx d 
                 JOIN users u ON d.donor_user_id = u.id 
                 LEFT JOIN blood_requests br ON d.request_id = br.id
                 ORDER BY d.timestamp DESC''')
    donations_history = c.fetchall()
    # Full history: all blood requests (with hospital name and status)
    c.execute('''SELECT br.id, u.full_name as hospital, br.blood_type, br.quantity, br.urgency, br.status, br.admin_approved, br.request_date, br.remaining_quantity
                 FROM blood_requests br JOIN users u ON br.hospital_user_id = u.id ORDER BY br.request_date DESC''')
    requests_history = c.fetchall()
    # Blockchain summary
    blocks = blockchain.chain
    conn.close()
    
    pending_hosp_html = ''.join(f'<tr><td>{h[1]}</td><td>{h[2]}</td><td>{h[3]}</td><td><a href="/approve_hospital/{h[0]}" class="btn btn-sm btn-success">Approve</a></td></tr>' for h in pending_hospitals)
    pending_req_html = ''.join(f'<tr><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td><a href="/approve_request/{r[0]}" class="btn btn-sm btn-success">Approve</a> <a href="/reject_request/{r[0]}" class="btn btn-sm btn-danger">Reject</a></td></tr>' for r in pending_requests)
    approved_hosp_html = ''.join(f'<li>{h[1]} - {h[2]}</li>' for h in approved_hospitals)
    
    donations_html = ''.join(f'<tr><td>{d[1]}</td><td>{d[2]}</td><td>{d[3]}</td><td>{d[4][:15]}...</td><td>{d[5]}</td><td>Request #{d[6] if d[6] else "N/A"}</td></tr>' for d in donations_history)
    requests_html = ''.join(f'<tr><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{"Approved" if r[6] else "Pending"}</td><td>{r[7]}</td><td>{r[8]}</td></tr>' for r in requests_history)
    
    content = f'''
    <div class="row">
        <div class="col-md-6"><div class="card mb-4"><div class="card-header bg-warning">Pending Hospital Approvals</div><div class="card-body"><table class="table"><thead><tr><th>Username</th><th>Hospital Name</th><th>Location</th><th>Action</th></tr></thead><tbody>{pending_hosp_html}</tbody></table></div></div></div>
        <div class="col-md-6"><div class="card mb-4"><div class="card-header bg-warning">Pending Blood Requests</div><div class="card-body"><table class="table"><thead><tr><th>Hospital</th><th>Blood Type</th><th>Quantity</th><th>Urgency</th><th>Date</th><th>Action</th></tr></thead><tbody>{pending_req_html}</tbody></table></div></div></div>
    </div>
    <div class="row mt-2">
        <div class="col-md-12"><div class="card mb-4"><div class="card-header bg-info">Approved Hospitals</div><div class="card-body"><ul>{approved_hosp_html}</ul></div></div></div>
    </div>
    <div class="row">
        <div class="col-md-12"><div class="card mb-4"><div class="card-header bg-secondary text-white">📜 Complete Blood Request History</div><div class="card-body"><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Hospital</th><th>Blood Type</th><th>Requested</th><th>Urgency</th><th>Status</th><th>Admin Approved</th><th>Date</th><th>Remaining</th></tr></thead><tbody>{requests_html}</tbody></table></div></div></div></div>
    </div>
    <div class="row">
        <div class="col-md-12"><div class="card mb-4"><div class="card-header bg-secondary text-white">💉 Complete Donation History</div><div class="card-body"><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Donor</th><th>Blood Type</th><th>Quantity</th><th>Tx Hash</th><th>Date</th><th>Request #</th></tr></thead><tbody>{donations_html}</tbody></table></div></div></div></div>
    </div>
    <div class="row">
        <div class="col-md-12"><div class="card"><div class="card-header bg-dark text-white">🔗 Blockchain Ledger</div><div class="card-body"><p>Chain valid: {blockchain.is_chain_valid()}</p><div style="height:200px; overflow-y:scroll;">{''.join(f'<div class="border-bottom p-1"><strong>Block #{b.index}:</strong> {b.transactions} <span class="text-muted">({b.timestamp})</span></div>' for b in blocks)}</div><a href="/view_blockchain" class="btn btn-sm btn-outline-primary mt-2">View Full Blockchain</a></div></div></div>
    </div>
    '''
    return render(content)

@app.route('/approve_hospital/<int:user_id>')
def approve_hospital(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_approved = 1 WHERE id = ? AND role = 'hospital'", (user_id,))
    conn.commit()
    conn.close()
    flash('Hospital approved', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/approve_request/<int:request_id>')
def approve_request(request_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE blood_requests SET admin_approved = 1, status = 'approved' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    flash('Blood request approved. Donors can now fulfill it.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/reject_request/<int:request_id>')
def reject_request(request_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE blood_requests SET status = 'rejected', admin_approved = 0 WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    flash('Blood request rejected', 'danger')
    return redirect(url_for('admin_dashboard'))

# --------------------------- BLOCKCHAIN VIEW ---------------------------
@app.route('/view_blockchain')
def view_blockchain():
    blocks_html = ''
    for b in blockchain.chain:
        blocks_html += f'''
        <div class="card mb-2"><div class="card-body">
            <strong>Block #{b.index}</strong><br>
            Transactions: {b.transactions}<br>
            Timestamp: {b.timestamp}<br>
            Previous Hash: {b.previous_hash[:20]}...<br>
            Hash: {b.hash[:20]}...
        </div></div>
        '''
    content = f'<h2>Blockchain Ledger</h2><p>Chain valid: {blockchain.is_chain_valid()}</p>{blocks_html}<a href="/" class="btn btn-secondary">Back</a>'
    return render(content)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)