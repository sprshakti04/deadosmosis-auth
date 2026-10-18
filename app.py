import os
import json
from datetime import datetime, timedelta
import secrets
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "deadosmosis_secret_key_12345")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

DB_FILE = "keys.json"

def load_keys():
    if not os.path.exists(DB_FILE):
        initial = {
            "DO-TEST-KEY-2026": {
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "lifetime",
                "duration_days": "lifetime",
                "expiry": "Lifetime",
                "hwid": "",
                "banned": False,
                "last_used": "Never"
            }
        }
        save_keys(initial)
        return initial
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_keys(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ----------------- API ENDPOINT FOR APK -----------------
@app.route("/api.php", methods=["GET", "POST"])
@app.route("/api", methods=["GET", "POST"])
def api_check():
    action = request.values.get("action", "")
    key = request.values.get("key", "").strip()
    hwid = request.values.get("hwid", "").strip()

    if action != "check":
        return jsonify({"status": "error", "message": "Invalid action"}), 400

    if not key:
        return jsonify({"status": "error", "message": "Please enter a key"}), 400

    keys = load_keys()
    if key not in keys:
        return jsonify({"status": "error", "message": "Invalid license key"})

    info = keys[key]

    if info.get("banned"):
        return jsonify({"status": "error", "message": "Key is suspended/banned"})

    if info.get("type") != "lifetime":
        expiry_dt = datetime.strptime(info["expiry"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiry_dt:
            return jsonify({"status": "error", "message": "License key has expired"})

    if hwid:
        if not info.get("hwid"):
            info["hwid"] = hwid
            info["first_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif info["hwid"] != hwid:
            return jsonify({"status": "error", "message": "Key bound to another device"})

    info["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_keys(keys)

    return jsonify({
        "status": "success",
        "message": "Authenticated successfully",
        "expiry": "Lifetime" if info.get("type") == "lifetime" else info.get("expiry")
    })

# ----------------- ADMIN DASHBOARD -----------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dead Osmosis - Key Panel</title>
    <style>
        body { background: #0c1017; color: #c9d1d9; font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 25px; }
        .container { max-width: 1000px; margin: auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 15px; margin-bottom: 25px; }
        h1 { margin: 0; color: #00B4FF; font-size: 24px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 25px; }
        .form-row { display: flex; gap: 15px; flex-wrap: wrap; }
        input[type=text], select, input[type=password] { background: #0d1117; border: 1px solid #30363d; color: #fff; padding: 10px 14px; border-radius: 6px; font-size: 14px; }
        .btn-primary { background: #00B4FF; color: #000; font-weight: bold; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #21262d; }
        th { background: #0d1117; color: #8b949e; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-active { background: #238636; color: #fff; }
        .badge-expired { background: #6e7681; color: #fff; }
        .badge-banned { background: #da3633; color: #fff; }
        .action-btn { background: none; border: 1px solid #30363d; color: #58a6ff; padding: 5px 10px; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>DEAD OSMOSIS KEY PANEL</h1>
                <small style="color: #8b949e;">API Endpoint: <code>{{ request.host_url }}api.php</code></small>
            </div>
            <a href="/logout" style="color: #ff5252; text-decoration: none; font-weight: bold;">LOGOUT</a>
        </div>
        <div class="card">
            <h3 style="margin-top:0; color:#58a6ff;">CREATE NEW LICENSE KEY</h3>
            <form method="POST" action="/create" class="form-row">
                <input type="text" name="custom_key" placeholder="Custom Key (Blank for Random)" style="flex: 1; min-width: 250px;">
                <select name="duration">
                    <option value="1">1 Day</option>
                    <option value="3">3 Days</option>
                    <option value="7" selected>7 Days</option>
                    <option value="15">15 Days</option>
                    <option value="30">30 Days</option>
                    <option value="lifetime">Lifetime</option>
                </select>
                <button type="submit" class="btn-primary">+ GENERATE KEY</button>
            </form>
        </div>
        <div class="card">
            <h3 style="margin-top:0; color:#58a6ff;">ALL KEYS ({{ keys|length }})</h3>
            <table>
                <thead>
                    <tr><th>Key</th><th>Expiry</th><th>HWID</th><th>Status</th><th>Last Used</th><th>Actions</th></tr>
                </thead>
                <tbody>
                    {% for k, v in keys.items() %}
                    <tr>
                        <td><strong style="color: #00B4FF; font-family: monospace;">{{ k }}</strong></td>
                        <td>{{ v.expiry }}</td>
                        <td><code>{{ v.hwid[:12] if v.hwid else 'Unbound' }}</code></td>
                        <td>
                            {% if v.banned %}
                                <span class="badge badge-banned">BANNED</span>
                            {% elif v.type != 'lifetime' and now > v.expiry %}
                                <span class="badge badge-expired">EXPIRED</span>
                            {% else %}
                                <span class="badge badge-active">ACTIVE</span>
                            {% endif %}
                        </td>
                        <td><small style="color: #8b949e;">{{ v.last_used }}</small></td>
                        <td>
                            <form method="POST" action="/action" style="display:inline;">
                                <input type="hidden" name="key" value="{{ k }}">
                                <button type="submit" name="act" value="hwid" class="action-btn">Reset HWID</button>
                                <button type="submit" name="act" value="ban" class="action-btn">{{ 'Unban' if v.banned else 'Ban' }}</button>
                                <button type="submit" name="act" value="delete" class="action-btn" style="color: #ff5252;">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - Dead Osmosis</title>
    <style>
        body { background: #0c1017; color: #fff; font-family: 'Segoe UI', Tahoma, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .box { background: #161b22; padding: 35px; border-radius: 12px; border: 1px solid #00B4FF; width: 300px; text-align: center; }
        input[type=password] { width: 100%; padding: 12px; margin: 15px 0; border-radius: 6px; border: 1px solid #30363d; background: #0d1117; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 12px; border: none; border-radius: 6px; background: #00B4FF; color: #000; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="box">
        <h2 style="color: #00B4FF; margin: 0;">DEAD OSMOSIS</h2>
        <p style="color: #8b949e; font-size: 13px;">Admin Panel Login</p>
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="Admin Password" required autofocus>
            <button type="submit">LOGIN</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/")
@app.route("/admin")
@app.route("/admin.php")
def admin_home():
    if not session.get("logged_in"):
        return render_template_string(LOGIN_TEMPLATE)
    keys = load_keys()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, keys=keys, now=now_str)

@app.route("/login", methods=["POST"])
def admin_login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["logged_in"] = True
    return redirect("/")

@app.route("/logout")
def admin_logout():
    session.clear()
    return redirect("/")

@app.route("/create", methods=["POST"])
def admin_create():
    if not session.get("logged_in"):
        return redirect("/")
    custom = request.form.get("custom_key", "").strip()
    duration = request.form.get("duration", "7")
    key = custom if custom else f"DO-{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"
    
    if duration == "lifetime":
        expiry = "Lifetime"
        t = "lifetime"
    else:
        days = int(duration)
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        t = "days"

    keys = load_keys()
    keys[key] = {
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": t,
        "duration_days": duration,
        "expiry": expiry,
        "hwid": "",
        "banned": False,
        "last_used": "Never"
    }
    save_keys(keys)
    return redirect("/")

@app.route("/action", methods=["POST"])
def admin_action():
    if not session.get("logged_in"):
        return redirect("/")
    k = request.form.get("key", "")
    act = request.form.get("act", "")
    keys = load_keys()
    if k in keys:
        if act == "delete":
            del keys[k]
        elif act == "hwid":
            keys[k]["hwid"] = ""
        elif act == "ban":
            keys[k]["banned"] = not keys[k].get("banned", False)
        save_keys(keys)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
