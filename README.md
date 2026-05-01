# 🌆 Chennai Smart City Pollution Monitor v2.0

Advanced intelligent pollution monitoring platform with real Chennai locations,
auto-alert generation, predictive analytics, and visual dashboards.

## Project Structure

```
smartcity_v2/
├── app.py
├── schema.sql
├── templates/
│   ├── base.html         ← shared layout (sidebar + topbar)
│   ├── dashboard.html
│   ├── logs.html
│   ├── alerts.html
│   ├── devices.html
│   └── analytics.html
└── static/
    └── css/
        └── style.css
```

## Setup

### 1. Install dependencies
```bash
pip install flask mysql-connector-python
```

### 2. Set up the database
```bash
mysql -u root -p < schema.sql
```

### 3. Update credentials in app.py
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "yourpassword",   # ← change this
    "database": "chennai_pollution_db"
}
```

### 4. Run
```bash
python app.py
```

### 5. Open browser
```
http://127.0.0.1:5000
```

## Features

| Feature | Details |
|---|---|
| Auto-alert generation | Every new SensorLog is scanned; alerts auto-created if above safe limit |
| Risk calculation | ratio = value / safe_limit → Safe / Medium / High / Critical |
| Pollution score | (value / safe_limit) × 100 |
| Trend detection | Compares last readings → Increasing / Decreasing / Stable |
| AI prediction | Rule-based → Critical Soon / Improving / Stable |
| Health impact | Mapped per pollutant type |
| 4 charts | Bar, Doughnut, Grouped bar, Horizontal bar (Chart.js) |
| Multi-page | Dashboard, Logs, Alerts, Devices, Analytics |
| Chennai data | 8 real Chennai locations with realistic pollution values |
