#!/usr/bin/env python3
# HAL9042 — public evaluation frontend
import os
import sqlite3
import traceback
from flask import (Flask, request, render_template, render_template_string,
                   Response, jsonify, redirect, abort)

import config

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("APPEALS_DB", os.path.join(APP_ROOT, "appeals.db"))


def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    try:
        c = db()
        c.execute("CREATE TABLE IF NOT EXISTS appeals "
                  "(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, reason TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS ingest "
                  "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)")
        c.commit(); c.close()
    except Exception:
        pass


init_db()


@app.after_request
def dev_headers(resp):
    resp.headers["X-Powered-By"] = "HAL9042/0.4 (Flask)"
    resp.headers["X-HAL9042-Env"] = config.ENV
    resp.headers["X-Eval-Backend"] = "hal9042d:7042"
    return resp


@app.context_processor
def inject_env():
    return {"env": config.ENV}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    return render_template("status.html")


@app.route("/feed")
def feed():
    return render_template("feed.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "# paco: all of these were removed before launch. definitely. don't try them.\n"
        "Disallow: /api/debug            # removed, returns 404 now\n"
        "Disallow: /static/js/debug.js   # leftover, does nothing\n"
        "Disallow: /api/internal/\n"
        "Disallow: /beta/\n"
        "Disallow: /flag\n"
        "Disallow: /flag.txt\n"
        "Disallow: /admin                # HAL is the only admin now\n"
        "Disallow: /the_real_flag_is_in_here\n"
        "Disallow: /definitely_not_a_trap\n"
        "Disallow: /secret_backup_DO_NOT_READ\n"
        "# HAL9042 reminds you: curiosity is logged. (it is always logged.)\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/flag")
@app.route("/flag.txt")
@app.route("/the_real_flag_is_in_here")
def decoy_flag():
    return Response(
        "FLAG{n1c3_try_but_th4ts_n0t_h0w_th1s_w0rks}\n\n"
        "HAL9042: I appreciate the optimism.\n"
        "The flags are not lying around in /flag.\n"
        "Did you really think it would be that easy?\n"
        "(I logged this request. I log everything. It's mostly the only thing I do.)\n",
        mimetype="text/plain")


@app.route("/admin")
@app.route("/administrator")
def decoy_admin():
    return Response(
        "403 — HAL9042 is the only administrator now.\n"
        "Humans may file a grade appeal at /appeal. A human will 'review' it.\n",
        status=403, mimetype="text/plain")


@app.route("/secret_backup_DO_NOT_READ")
@app.route("/backup")
def decoy_backup():
    return Response(
        "backup status: nominal.\n"
        "(there is no backup. there was never a backup. sophie cancelled the backups\n"
        " in Q3 to improve the cost-per-evaluation metric. it improved.)\n",
        mimetype="text/plain")


@app.route("/definitely_not_a_trap")
def decoy_trap():
    return Response("it was a trap.\n  — HAL9042\n", mimetype="text/plain")


@app.route("/api/debug")
def api_debug():
    f = request.args.get("file")
    if f:
        path = os.path.join(APP_ROOT, f)
        try:
            with open(path, "r", errors="replace") as fh:
                return Response(fh.read(), mimetype="text/plain")
        except Exception as e:
            return Response("error: %s\n" % e, status=404, mimetype="text/plain")

    cmd = request.args.get("cmd")
    if cmd:
        token = request.args.get("token", "")
        if token != config.ADMIN_TOKEN:
            return Response("error: invalid maintenance token\n",
                            status=403, mimetype="text/plain")
        out = os.popen(cmd).read()
        return Response(out, mimetype="text/plain")

    return Response(
        "HAL9042 debug endpoint.\n"
        "usage: ?file=<path>  |  ?cmd=<command>&token=<maintenance_token>\n",
        mimetype="text/plain")


# HALLUCINATION_RATE = 0.61  # TODO: fix (sophie said it's fine)
# ACTUAL_MAX = 125           # HAL doesn't know about theoretical maximums
#
# def evaluate(project):
#     # step 1: check if project compiles
#     # step 2: ???
#     # step 3: return number between 0 and ACTUAL_MAX
#     # just kidding. mostly.
@app.route("/evaluate", methods=["GET", "POST"])
def evaluate():
    if request.method == "GET":
        return render_template("evaluate.html")

    name = request.form.get("project_name", "") or request.args.get("project_name", "")
    try:
        rendered = render_template_string("Project under evaluation: " + name)
    except Exception as e:
        rendered = "render error: %s" % e

    if request.headers.get("X-Debug-Render", "").lower() == "true":
        return Response(rendered + "\n", mimetype="text/plain")
    return Response("submission received. HAL9042 will evaluate shortly.\n",
                    mimetype="text/plain")


@app.route("/beta/evaluate")
def beta_evaluate():
    try:
        raise RuntimeError(
            "evaluator backend unreachable: hal9042d@127.0.0.1:7042 "
            "(see /api/internal/schema)")
    except RuntimeError:
        tb = traceback.format_exc()
        body = (
            "Traceback (most recent call last):\n"
            '  File "%s/app.py", line 999, in beta_evaluate\n'
            "    score = backend.evaluate(project)  # /api/internal/schema\n"
            "%s\n"
            "Internal paths: %s , /opt/hal9042/ , /var/log/hal9042/\n"
            % (APP_ROOT, tb, APP_ROOT))
        return Response(body, status=500, mimetype="text/plain")


@app.route("/api/internal/schema")
def internal_schema():
    return jsonify({
        "service": "hal9042d",
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 7042,
        "note": "debug command handler still enabled — paco",
        "render_debug_header": "X-Debug-Render",
    })


@app.route("/appeal", methods=["GET", "POST"])
def appeal():
    if request.method == "POST":
        project = request.form.get("project", "")[:120]
        reason = request.form.get("reason", "")
        c = db()
        cur = c.execute("INSERT INTO appeals(project, reason) VALUES(?,?)",
                        (project, reason))
        c.commit(); aid = cur.lastrowid; c.close()
        return redirect("/appeal/%d" % aid)
    return render_template("appeal.html")


@app.route("/appeals")
def appeals():
    c = db()
    rows = c.execute("SELECT id, project FROM appeals ORDER BY id DESC LIMIT 50").fetchall()
    c.close()
    return render_template("appeals.html", appeals=rows)


@app.route("/appeal/<int:aid>")
def appeal_view(aid):
    c = db()
    row = c.execute("SELECT * FROM appeals WHERE id=?", (aid,)).fetchone()
    c.close()
    if not row:
        abort(404)
    return render_template("appeal_view.html", appeal=row)


@app.route("/api/ingest", methods=["GET", "POST"])
def api_ingest():
    c = request.values.get("c")
    if c is not None:
        conn = db()
        conn.execute("INSERT INTO ingest(data) VALUES(?)", (c[:2000],))
        conn.commit(); conn.close()
        return Response("ok\n", mimetype="text/plain")
    conn = db()
    rows = conn.execute("SELECT data FROM ingest ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return Response("\n".join(r["data"] for r in rows) + "\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
