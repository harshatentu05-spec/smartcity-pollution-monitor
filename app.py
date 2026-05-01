"""
Chennai Smart City Pollution Monitoring System
Advanced intelligent monitoring platform with analytics and prediction
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = "chennai_smartcity_2025"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Harsha@2005",   # ← Change this
    "database": "chennai_pollution_db"
}

# ── Safe limits per pollutant (WHO standards) ──────────────────
SAFE_LIMITS = {
    "CO2":   400.0,
    "NO2":    40.0,
    "PM2.5":  25.0,
    "SO2":    20.0,
    "CO":     10.0,
}

# ── Health impact mapping ──────────────────────────────────────
HEALTH_IMPACT = {
    "CO2":   "Breathing issues, dizziness, reduced concentration",
    "NO2":   "Respiratory irritation, lung inflammation",
    "PM2.5": "Lung damage, cardiovascular disease risk",
    "SO2":   "Throat irritation, asthma aggravation",
    "CO":    "Oxygen reduction, carbon monoxide poisoning",
}

# ── Chennai locations ──────────────────────────────────────────
CHENNAI_LOCATIONS = [
    "T Nagar", "Anna Nagar", "Adyar", "Velachery",
    "Guindy", "OMR IT Corridor", "Central Station", "Chennai Airport"
]


def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"[DB ERROR] {e}")
        return None


# ── Risk calculation ───────────────────────────────────────────
def calculate_risk(value, pollutant):
    limit = SAFE_LIMITS.get(pollutant, 100)
    ratio = float(value) / float(limit)
    if ratio <= 1.0:   return "Safe",     "#22c55e", ratio
    if ratio <= 1.5:   return "Medium",   "#f59e0b", ratio
    if ratio <= 2.0:   return "High",     "#f97316", ratio
    return               "Critical", "#ef4444", ratio


# ── Pollution score ────────────────────────────────────────────
def pollution_score(value, pollutant):
    limit = SAFE_LIMITS.get(pollutant, 100)
    return round((float(value) / float(limit)) * 100, 1)


# ── Trend & prediction ─────────────────────────────────────────
def get_trend_and_prediction(cursor, pollutant, device_id):
    cursor.execute("""
        SELECT Value FROM SensorLog
        WHERE PollutionType=%s AND DeviceID=%s
        ORDER BY logged_time DESC LIMIT 5
    """, (pollutant, device_id))
    rows = [r["Value"] for r in cursor.fetchall()]
    if len(rows) < 2:
        return "Stable", "Stable"
    trend = "Increasing" if rows[0] > rows[1] else "Decreasing" if rows[0] < rows[1] else "Stable"
    if len(rows) >= 3 and rows[0] > rows[1] > rows[2]:
        prediction = "Critical Soon"
    elif len(rows) >= 3 and rows[0] < rows[1] < rows[2]:
        prediction = "Improving"
    else:
        prediction = "Stable"
    return trend, prediction


# ── Auto-generate alerts for unprocessed logs ──────────────────
def auto_generate_alerts(conn, cursor):
    cursor.execute("""
        SELECT sl.LogID, sl.PollutionType, sl.Value, sl.DeviceID
        FROM SensorLog sl
        LEFT JOIN RiskAlert ra ON sl.LogID = ra.LogID
        WHERE ra.AlertID IS NULL
    """)
    new_logs = cursor.fetchall()
    for log in new_logs:
        level, _, ratio = calculate_risk(log["Value"], log["PollutionType"])
        if level == "Safe":
            continue
        msg = f"{log['PollutionType']} at {ratio:.1f}x safe limit — {HEALTH_IMPACT.get(log['PollutionType'], '')}"
        cursor.execute("""
            INSERT INTO RiskAlert (LogID, AlertLevel, AlertMessage)
            VALUES (%s, %s, %s)
        """, (log["LogID"], level, msg))
    conn.commit()


# ════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════
@app.route("/")
def dashboard():
    conn = get_connection()
    if not conn:
        return "<h2 style='color:red;padding:40px'>❌ DB connection failed. Check DB_CONFIG in app.py</h2>", 500

    cursor = conn.cursor(dictionary=True)
    auto_generate_alerts(conn, cursor)

    cursor.execute("SELECT COUNT(*) AS t FROM SensorDevice"); total_devices = cursor.fetchone()["t"]
    cursor.execute("SELECT COUNT(*) AS t FROM SensorLog");    total_logs    = cursor.fetchone()["t"]
    cursor.execute("SELECT COUNT(*) AS t FROM RiskAlert");    total_alerts  = cursor.fetchone()["t"]
    cursor.execute("SELECT COUNT(*) AS t FROM RiskAlert WHERE AlertLevel='Critical'"); critical = cursor.fetchone()["t"]

    # Latest 5 logs enriched
    cursor.execute("""
        SELECT sl.LogID, sl.PollutionType, sl.Value, sl.logged_time,
               sd.LocationName, sl.DeviceID
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        ORDER BY sl.logged_time DESC LIMIT 5
    """)
    raw_logs = cursor.fetchall()
    latest_logs = []
    for l in raw_logs:
        risk, color, ratio = calculate_risk(l["Value"], l["PollutionType"])
        score = pollution_score(l["Value"], l["PollutionType"])
        latest_logs.append({**l, "risk": risk, "color": color, "score": score})

    # Recent alerts
    cursor.execute("""
        SELECT ra.AlertID, ra.AlertLevel, ra.AlertMessage,
               sl.PollutionType, sl.Value, sl.logged_time, sd.LocationName
        FROM RiskAlert ra
        JOIN SensorLog sl ON ra.LogID=sl.LogID
        JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        ORDER BY sl.logged_time DESC LIMIT 6
    """)
    recent_alerts = cursor.fetchall()

    # Location pollution scores for map cards
    cursor.execute("""
        SELECT sd.LocationName,
               AVG(sl.Value) AS avg_val,
               sl.PollutionType,
               MAX(sl.logged_time) AS last_seen
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        GROUP BY sd.LocationName, sl.PollutionType
        ORDER BY avg_val DESC LIMIT 8
    """)
    location_stats = cursor.fetchall()

    cursor.close(); conn.close()
    return render_template("dashboard.html",
        total_devices=total_devices, total_logs=total_logs,
        total_alerts=total_alerts, critical=critical,
        latest_logs=latest_logs, recent_alerts=recent_alerts,
        location_stats=location_stats)


# ════════════════════════════════════════════════════════════════
# SENSOR LOGS
# ════════════════════════════════════════════════════════════════
@app.route("/logs")
def logs():
    conn = get_connection()
    if not conn: return redirect(url_for("dashboard"))
    cursor = conn.cursor(dictionary=True)
    auto_generate_alerts(conn, cursor)

    cursor.execute("""
        SELECT sl.LogID, sl.PollutionType, sl.Value, sl.logged_time,
               sd.LocationName, sd.DeviceID
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        ORDER BY sl.logged_time DESC
    """)
    raw = cursor.fetchall()
    all_logs = []
    for l in raw:
        risk, color, ratio = calculate_risk(l["Value"], l["PollutionType"])
        score = pollution_score(l["Value"], l["PollutionType"])
        trend, pred = get_trend_and_prediction(cursor, l["PollutionType"], l["DeviceID"])
        health = HEALTH_IMPACT.get(l["PollutionType"], "—")
        all_logs.append({**l, "risk": risk, "color": color, "score": score,
                         "trend": trend, "prediction": pred, "health": health})

    cursor.execute("SELECT DeviceID, LocationName FROM SensorDevice ORDER BY DeviceID")
    devices = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("logs.html", all_logs=all_logs, devices=devices,
                           pollutants=list(SAFE_LIMITS.keys()))


# ════════════════════════════════════════════════════════════════
# ALERTS
# ════════════════════════════════════════════════════════════════
@app.route("/alerts")
def alerts():
    conn = get_connection()
    if not conn: return redirect(url_for("dashboard"))
    cursor = conn.cursor(dictionary=True)
    auto_generate_alerts(conn, cursor)

    cursor.execute("""
        SELECT ra.AlertID, ra.AlertLevel, ra.AlertMessage,
               sl.PollutionType, sl.Value, sl.logged_time,
               sd.LocationName
        FROM RiskAlert ra
        JOIN SensorLog sl ON ra.LogID=sl.LogID
        JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        ORDER BY FIELD(ra.AlertLevel,'Critical','High','Medium','Low'),
                 sl.logged_time DESC
    """)
    all_alerts = cursor.fetchall()

    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for a in all_alerts:
        counts[a["AlertLevel"]] = counts.get(a["AlertLevel"], 0) + 1

    cursor.close(); conn.close()
    return render_template("alerts.html", all_alerts=all_alerts, counts=counts,
                           health_impact=HEALTH_IMPACT)


# ════════════════════════════════════════════════════════════════
# DEVICES
# ════════════════════════════════════════════════════════════════
@app.route("/devices")
def devices():
    conn = get_connection()
    if not conn: return redirect(url_for("dashboard"))
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT sd.DeviceID, sd.LocationName,
               COUNT(sl.LogID) AS log_count,
               MAX(sl.logged_time) AS last_seen,
               AVG(sl.Value) AS avg_val
        FROM SensorDevice sd
        LEFT JOIN SensorLog sl ON sd.DeviceID=sl.DeviceID
        GROUP BY sd.DeviceID, sd.LocationName
        ORDER BY sd.DeviceID
    """)
    all_devices = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("devices.html", all_devices=all_devices)


# ════════════════════════════════════════════════════════════════
# ANALYTICS
# ════════════════════════════════════════════════════════════════
@app.route("/analytics")
def analytics():
    conn = get_connection()
    if not conn: return redirect(url_for("dashboard"))
    cursor = conn.cursor(dictionary=True)
    auto_generate_alerts(conn, cursor)

    # Avg value per location
    cursor.execute("""
        SELECT sd.LocationName, AVG(sl.Value) AS avg_val
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        GROUP BY sd.LocationName ORDER BY avg_val DESC
    """)
    by_location = cursor.fetchall()

    # Avg value per pollutant
    cursor.execute("""
        SELECT sl.PollutionType, AVG(sl.Value) AS avg_val,
               MAX(sl.Value) AS max_val, MIN(sl.Value) AS min_val
        FROM SensorLog sl GROUP BY sl.PollutionType
    """)
    by_pollutant = cursor.fetchall()

    # Time trend (last 10 logs)
    cursor.execute("""
        SELECT sl.logged_time, sl.PollutionType, sl.Value, sd.LocationName
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        ORDER BY sl.logged_time DESC LIMIT 20
    """)
    time_trend = cursor.fetchall()

    # Risk distribution
    cursor.execute("""
        SELECT AlertLevel, COUNT(*) AS cnt
        FROM RiskAlert GROUP BY AlertLevel
    """)
    risk_dist = {r["AlertLevel"]: r["cnt"] for r in cursor.fetchall()}

    # Pollution scores per location
    cursor.execute("""
        SELECT sd.LocationName, sl.PollutionType, AVG(sl.Value) AS avg_val
        FROM SensorLog sl JOIN SensorDevice sd ON sl.DeviceID=sd.DeviceID
        GROUP BY sd.LocationName, sl.PollutionType
    """)
    scores_raw = cursor.fetchall()
    location_scores = {}
    for r in scores_raw:
        loc = r["LocationName"]
        score = pollution_score(r["avg_val"], r["PollutionType"])
        location_scores[loc] = max(location_scores.get(loc, 0), score)

    cursor.close(); conn.close()
    return render_template("analytics.html",
        by_location=by_location, by_pollutant=by_pollutant,
        time_trend=time_trend, risk_dist=risk_dist,
        location_scores=location_scores, safe_limits=SAFE_LIMITS)


# ════════════════════════════════════════════════════════════════
# ADD ALERT (form POST)
# ════════════════════════════════════════════════════════════════
@app.route("/add-alert", methods=["POST"])
def add_alert():
    conn = get_connection()
    if not conn:
        flash("❌ DB connection failed.", "danger"); return redirect(url_for("alerts"))
    cursor = conn.cursor()
    device_id = request.form.get("device_id")
    ptype     = request.form.get("pollution_type")
    value     = request.form.get("value")
    cursor.execute("""
        INSERT INTO SensorLog (DeviceID, PollutionType, Value, logged_time)
        VALUES (%s, %s, %s, NOW())
    """, (device_id, ptype, value))
    conn.commit()
    cursor.close(); conn.close()
    flash(f"✅ Sensor log added — alert auto-generated if threshold exceeded.", "success")
    return redirect(url_for("alerts"))


# ════════════════════════════════════════════════════════════════
# API: live stats for auto-refresh
# ════════════════════════════════════════════════════════════════
@app.route("/api/stats")
def api_stats():
    conn = get_connection()
    if not conn: return jsonify({"error": "db"}), 500
    cursor = conn.cursor(dictionary=True)
    auto_generate_alerts(conn, cursor)
    cursor.execute("SELECT COUNT(*) AS t FROM SensorLog");  tl = cursor.fetchone()["t"]
    cursor.execute("SELECT COUNT(*) AS t FROM RiskAlert");  ta = cursor.fetchone()["t"]
    cursor.execute("SELECT COUNT(*) AS t FROM RiskAlert WHERE AlertLevel='Critical'"); tc = cursor.fetchone()["t"]
    cursor.close(); conn.close()
    return jsonify({"total_logs": tl, "total_alerts": ta, "critical": tc})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
