from flask import Flask, request, jsonify, json, render_template, g
import pathlib
import re
import sqlite3
import pandas as pd
import logging.config

LOG_FILENAME = "./error.log"
# directory where the saved files are located
WORK_DIR = "work"
# name of the SQLite database
DB_FILE = "./db.sqlite"
# name of the table in database
TABLE_NAME = "master"
# columns in database that are not used
IGNORE_COLS = ["id", "source", "cache sizes"]
# columns in database used for determining plot
PLOT_CONTROLS = ["workload", "devices", "algorithms", "write policy"]
# default x and y axis for the chart
DEF_XAXIS = "total purchase cost ($)"
DEF_YAXIS = "avg throughput (KB/s)"

logging.config.dictConfig({
    "version": 1,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_FILENAME,
            "mode": "a",
            "formatter": "default"
        }
    },
    "root": {
        "level": "ERROR",
        "handlers": ["file"]
    }
})

def get_trace(cur, query, params):
    cur.execute(query, tuple(params[i] for i in PLOT_CONTROLS))
    df = pd.DataFrame(cur.fetchall())

    if df.empty:
        raise ValueError("No data found for the specified parameters.")
    return {
        "x": df[0].tolist(),
        "y": df[1].tolist(),
        # the trace is a scatter plot when there are more than 2 devices and a line otherwise
        "mode": "markers" if (len(params["devices"].split('-')) > 2) else "lines+markers",
        # name to be displayed in legend
        "name": ' '.join([params[i] for i in PLOT_CONTROLS]),
        # data displayed when hovering over point
        "hovertext": df[2].tolist(),
        # use WebGL for performance because there could be a lot of plotted data
        "type": "scattergl",
        "showlegend": True
    }

## static variable to hold the SQL query for get_trace
## Note: we include 'cache sizes' so that it can be displayed when hovering over a point
get_trace.sql_query = f"""SELECT {{}}, `cache sizes` FROM {TABLE_NAME} WHERE ({' AND '.join(map(lambda x: f"`{x}`=?", PLOT_CONTROLS))});"""

app = Flask(__name__)

# handle SQLite db connections
def get_conn():
    conn = getattr(g, "conn", None)
    if conn is None:
        g.conn = sqlite3.connect(DB_FILE)
        conn = g.conn
    return conn

@app.teardown_appcontext
def close_conn(exception):
    conn = getattr(g, "conn", None)
    if conn is not None:
        conn.close()

@app.route("/initplot", methods=["GET"])
def init_plot():
    res = None
    code = 200
    try:
        conn = get_conn()
        cur = conn.cursor()
        unique_col_vals = {}
        sql_get_unique_col_vals = f"SELECT DISTINCT `{{}}` FROM {TABLE_NAME};"
        for i in PLOT_CONTROLS:
            cur.execute(sql_get_unique_col_vals.format(i))
            col_vals = cur.fetchall()
            col_vals = [v[0] for v in col_vals]
            col_vals.sort()
            unique_col_vals[i] = col_vals

        # PRAGMA is a SQLite-specific query to get metadata
        cur.execute(f"PRAGMA table_info({TABLE_NAME});")
        col_names = [c[1] for c in cur.fetchall()]
        axis_opts = list(filter(lambda x: not((x in IGNORE_COLS) or (x in PLOT_CONTROLS)), col_names))
        axis_opts.sort()

        entries = sorted(pathlib.Path(WORK_DIR).iterdir())
        saved_files = []
        for e in entries:
            if e.is_file():
                saved_files.append(e.name)

        res = {"controls": unique_col_vals,
               "xaxis": {"opts": axis_opts, "def": DEF_XAXIS},
               "yaxis": {"opts": axis_opts, "def": DEF_YAXIS},
               "files": saved_files}
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": "An unexpected error occurred during initialization."}
        code = 500
    return jsonify(res), code

@app.route("/plot", methods=["POST"])
def plot():
    res = None
    code = 200
    data = request.get_json()
    try:
        if data is None:
            raise ValueError("No data received.")

        conn = get_conn()
        cur = conn.cursor()
        # set the axes columns to be returned from query
        query = get_trace.sql_query.format(','.join(map(lambda x: f"`{x}`", data["axes"])))
        res = {
            "trace": get_trace(cur, query, data["plot"])
        }
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": str(e)}
        code = 500
    return jsonify(res), code

@app.route("/validconfigs", methods=["POST"])
def valid_configs():
    res = None
    code = 200
    data = request.get_json()
    try:
        if data is None:
            raise ValueError("No data received.")

        cond_keys = []
        cond_vals = ()
        for i in data.items():
            cond_keys.append(i[0])
            cond_vals += (i[1],)

        conn = get_conn()
        cur = conn.cursor()
        config_cond = ' AND '.join(map(lambda x: f"`{x}`=?", cond_keys))
        sql_get_valid_configs = f"SELECT DISTINCT `{{}}` FROM {TABLE_NAME} WHERE ({config_cond});"
        res = {}
        ret_cols = filter(lambda x: not(x in cond_keys), PLOT_CONTROLS)
        for i in ret_cols:
            cur.execute(sql_get_valid_configs.format(i), cond_vals)
            col_vals = cur.fetchall()
            col_vals = [v[0] for v in col_vals]
            col_vals.sort()
            res[i.replace(' ', '-')] = col_vals

    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": str(e)}
        code = 500
    return jsonify(res), code

@app.route("/changeaxes", methods=["POST"])
def change_axes():
    res = None
    code = 200
    data = request.get_json()
    try:
        if data is None:
            raise ValueError("No data received.")

        conn = get_conn()
        cur = conn.cursor()
        ret_cols = []
        # False indicates axis is not present and True to indicate presence
        axes_set = [False, False]
        for i, a in enumerate(["xaxis", "yaxis"]):
            v = data["axes"].get(a, None)
            if not(v is None):
                ret_cols.append(v)
                axes_set[i] = True

        ret_cols = ','.join(map(lambda x: f"`{x}`", ret_cols))
        trace_cond = ' AND '.join(map(lambda x: f"`{x}`=?", PLOT_CONTROLS))
        sql_get_axes = f"SELECT {ret_cols} FROM {TABLE_NAME} WHERE ({trace_cond});"
        res = []
        for t in data["traces"]:
            cur.execute(sql_get_axes, tuple(t[i] for i in PLOT_CONTROLS))
            df = pd.DataFrame(cur.fetchall())
            t_update = {}
            if axes_set[0]:
                t_update['x'] = [df[0].tolist()]
            if axes_set[1]:
                t_update['y'] = [df[1 if axes_set[0] else 0].tolist()]
            res.append(t_update)
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": str(e)}
        code = 500
    return jsonify(res), code

@app.route("/open/<string:filename>", methods=["GET"])
def load_plot(filename):
    res = None
    code = 200
    try:
        filepath = WORK_DIR / pathlib.Path(filename)
        with filepath.open('r') as f:
            chart = json.load(f)
            
            conn = get_conn()
            cur = conn.cursor()
            # this a little more performant by reusing the sql_query template string for getting each trace from the database 
            query = get_trace.sql_query.format(','.join(map(lambda x: f"`{x}`", chart["axes"])))
            traces = []
            for t in chart["traces"]:
                traces.append(get_trace(cur, query, t))

            res = {
                "traces": traces,
                "axes": chart["axes"]
            }
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": "An error occurred trying to open chart file."}
        code = 500
    return jsonify(res), code

@app.route("/delete/<string:filename>", methods=["DELETE"])
def delete_plot(filename):
    res = None
    code = 200
    try:
        filepath = WORK_DIR / pathlib.Path(filename)
        filepath.unlink()
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": "An error occurred trying to delete chart file."}
        code = 500
    return jsonify(res), code

@app.route("/save/<string:filename>", methods=["POST"])
def save_plot(filename):
    res = None
    code = 201
    data = request.get_json()
    try:
        if data is None:
            raise ValueError("No data received.")

        filepath = WORK_DIR / pathlib.Path(filename)
        # this would fail if filename is not valid or if there are other problems such as permissions
        with filepath.open('w') as f:
            json.dump(data, f)
    except Exception as e:
        app.logger.error("Error occurred!", exc_info=True)
        res = {"message": "An error occurred trying to save this chart."}
        code = 500
    return jsonify(res), code

@app.route('/', defaults={"path": ''}, methods=["GET"])
@app.route("/<path:path>")
def show_plot(path):
    return render_template("master-plotter.html", controls=PLOT_CONTROLS), 200
