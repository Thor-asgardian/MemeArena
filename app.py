import os
import json
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif","webp"}

app = Flask(__name__)
app.secret_key = "replace-this-with-a-secure-random-key"  # change for production
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def read_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def write_data(data):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DATA_FILE)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        data = read_data()
        user = data["users"].get(session["username"])
        if not user or not user.get("is_admin"):
            flash("Admin access required.", "danger")
            return redirect(url_for("feed"))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ---------------------
# Routes
# ---------------------

@app.route("/")
def home():
    return redirect(url_for("feed"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Provide username and password.", "warning")
            return redirect(url_for("register"))

        data = read_data()
        if username in data["users"]:
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        data["users"][username] = {"password_hash": password_hash, "is_admin": False}
        write_data(data)
        flash("Registered! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("rgs_page.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        data = read_data()
        user = data["users"].get(username)
        if user and check_password_hash(user["password_hash"], password):
            session["username"] = username
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("feed"))
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/uploads", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        caption = request.form.get("caption", "").strip()
        file = request.files.get("image")
        if not file or file.filename == "":
            flash("Please select an image file.", "warning")
            return redirect(url_for("upload"))
        if not allowed_file(file.filename):
            flash("File type not allowed.", "danger")
            return redirect(url_for("upload"))

        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        data = read_data()
        meme_id = data.get("next_meme_id", 1)
        meme = {
            "id": meme_id,
            "caption": caption,
            "image": filename,
            "author": session["username"],
            "created_at": datetime.utcnow().isoformat(),
            "votes": {}  # user -> 1 or -1
        }
        data["memes"].append(meme)
        data["next_meme_id"] = meme_id + 1
        write_data(data)
        flash("Meme uploaded!", "success")
        return redirect(url_for("feed"))

    return render_template("upload.html")

@app.route("/feed")
def feed():
    data = read_data()
    memes = data.get("memes", [])
    # compute score for each meme
    for m in memes:
        m["score"] = sum(m.get("votes", {}).values()) if m.get("votes") else 0
        # determine current user's vote
        m["my_vote"] = 0
        if "username" in session:
            m["my_vote"] = m.get("votes", {}).get(session["username"], 0)
    # show newest first
    memes = sorted(memes, key=lambda x: x["created_at"], reverse=True)
    return render_template("feed.html", memes=memes)

@app.route("/vote/<int:meme_id>", methods=["POST"])
@login_required
def vote(meme_id):
    action = request.form.get("action")  # "up" or "down"
    if action not in ("up", "down"):
        return ("Bad Request", 400)
    data = read_data()
    memes = data.get("memes", [])
    meme = next((m for m in memes if m["id"] == meme_id), None)
    if not meme:
        flash("Meme not found.", "danger")
        return redirect(url_for("feed"))

    user = session["username"]
    current = meme.get("votes", {}).get(user, 0)
    new_vote = 1 if action == "up" else -1

    if current == new_vote:
        # toggle off
        meme["votes"].pop(user, None)
    else:
        meme.setdefault("votes", {})[user] = new_vote

    write_data(data)
    return redirect(url_for("feed"))

@app.route("/delete/<int:meme_id>", methods=["POST"])
@admin_required
def delete_meme(meme_id):
    data = read_data()
    memes = data.get("memes", [])
    meme = next((m for m in memes if m["id"] == meme_id), None)
    if not meme:
        flash("Meme not found.", "danger")
        return redirect(url_for("feed"))
    # remove image file if exists
    try:
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], meme["image"])
        if os.path.exists(img_path):
            os.remove(img_path)
    except Exception as e:
        app.logger.error("Error deleting image: %s", e)
    data["memes"] = [m for m in memes if m["id"] != meme_id]
    write_data(data)
    flash("Meme deleted.", "info")
    return redirect(url_for("feed"))

# Serve uploaded images directly (Flask static could already do this, but route is explicit)
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------------
# Run
# ---------------------
if __name__ == "__main__":
    # create data file if missing
    if not os.path.exists(DATA_FILE):
        initial = {"users": {}, "memes": [], "next_meme_id": 1}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2)
    app.run(debug=True)