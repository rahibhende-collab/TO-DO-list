from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import date

app = Flask(__name__)
app.secret_key = "1234"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "todo.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Personal',
                priority TEXT NOT NULL DEFAULT 'Medium'
                    CHECK(priority IN ('Low', 'Medium', 'High')),
                due_date TEXT DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)


@app.route("/")
def index():
    status = request.args.get("status", "all")
    category = request.args.get("category", "all")
    search = request.args.get("q", "").strip()

    where = []
    params = []

    if status == "pending":
        where.append("completed = 0")
    elif status == "completed":
        where.append("completed = 1")

    if category != "all":
        where.append("category = ?")
        params.append(category)

    if search:
        where.append("(title LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        ORDER BY
            completed ASC,
            CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            CASE WHEN due_date = '' THEN 1 ELSE 0 END,
            due_date ASC,
            id DESC
    """

    with get_db() as conn:
        tasks = conn.execute(sql, params).fetchall()
        stats = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN completed = 0 AND due_date <> ''
                                  AND due_date < ? THEN 1 ELSE 0 END) AS overdue
            FROM tasks
        """, (date.today().isoformat(),)).fetchone()
        categories = conn.execute(
            "SELECT DISTINCT category FROM tasks ORDER BY category"
        ).fetchall()

    return render_template(
        "index.html",
        tasks=tasks,
        stats=stats,
        categories=categories,
        current_status=status,
        current_category=category,
        search=search,
        today=date.today().isoformat()
    )


@app.route("/add", methods=["POST"])
def add_task():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Please enter a task title.", "error")
        return redirect(url_for("index"))

    description = request.form.get("description", "").strip()
    category = request.form.get("category", "Personal").strip() or "Personal"
    priority = request.form.get("priority", "Medium")
    if priority not in ("Low", "Medium", "High"):
        priority = "Medium"
    due_date = request.form.get("due_date", "").strip()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO tasks (title, description, category, priority, due_date)
            VALUES (?, ?, ?, ?, ?)
        """, (title, description, category, priority, due_date))

    flash("Task added successfully.", "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    with get_db() as conn:
        conn.execute("""
            UPDATE tasks SET completed = CASE completed WHEN 0 THEN 1 ELSE 0 END
            WHERE id = ?
        """, (task_id,))
    flash("Task status updated.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    with get_db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            flash("Task not found.", "error")
            return redirect(url_for("index"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if not title:
                flash("Task title cannot be empty.", "error")
                return render_template("edit.html", task=task)

            description = request.form.get("description", "").strip()
            category = request.form.get("category", "Personal").strip() or "Personal"
            priority = request.form.get("priority", "Medium")
            if priority not in ("Low", "Medium", "High"):
                priority = "Medium"
            due_date = request.form.get("due_date", "").strip()

            conn.execute("""
                UPDATE tasks
                SET title = ?, description = ?, category = ?, priority = ?, due_date = ?
                WHERE id = ?
            """, (title, description, category, priority, due_date, task_id))
            flash("Task updated successfully.", "success")
            return redirect(url_for("index"))

    return render_template("edit.html", task=task)


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    flash("Task deleted.", "success")
    return redirect(url_for("index"))


@app.route("/clear-completed", methods=["POST"])
def clear_completed():
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE completed = 1")
    flash("Completed tasks cleared.", "success")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
