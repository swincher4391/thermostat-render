#!/usr/bin/env python3
"""
Simple dashboard for thermostat and gas usage data
Run: python dashboard.py
View: http://localhost:5000
"""

import os
import psycopg2
from flask import Flask, render_template_string, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atmos Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        h1 { margin-bottom: 20px; color: #00d4ff; }
        h2 { margin: 20px 0 10px; color: #888; font-size: 14px; text-transform: uppercase; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
        }
        .stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-value { font-size: 32px; font-weight: bold; color: #00d4ff; }
        .stat-label { font-size: 12px; color: #888; margin-top: 5px; }
        .stat.heating .stat-value { color: #ff6b6b; }
        .stat.cool .stat-value { color: #4ecdc4; }
        .chart-container { height: 300px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
        th { color: #888; font-size: 12px; text-transform: uppercase; }
        .refresh-btn {
            background: #00d4ff;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #00b8e6; }
        .heating-on { color: #ff6b6b; }
        .heating-off { color: #4ecdc4; }
    </style>
</head>
<body>
    <h1>Atmos Dashboard</h1>
    <button class="refresh-btn" onclick="location.reload()">Refresh Data</button>

    <div class="stat-grid">
        <div class="stat">
            <div class="stat-value" id="indoor-temp">--</div>
            <div class="stat-label">Indoor Temp (°F)</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="outdoor-temp">--</div>
            <div class="stat-label">Outdoor Temp (°F)</div>
        </div>
        <div class="stat" id="heating-stat">
            <div class="stat-value" id="heating-status">--</div>
            <div class="stat-label">Heating Status</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="humidity">--</div>
            <div class="stat-label">Humidity (%)</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Temperature (Last 24 Hours)</h2>
            <div class="chart-container">
                <canvas id="tempChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>Heating Activity</h2>
            <div class="chart-container">
                <canvas id="heatingChart"></canvas>
            </div>
        </div>
    </div>

    <h2>Gas Meter Readings</h2>
    <div class="card">
        <table>
            <thead>
                <tr><th>Date/Time</th><th>Reading</th><th>CCF Used</th></tr>
            </thead>
            <tbody id="gas-table"></tbody>
        </table>
    </div>

    <h2>Recent Thermostat Readings</h2>
    <div class="card">
        <table>
            <thead>
                <tr><th>Time</th><th>Indoor</th><th>Outdoor</th><th>Adjusted</th><th>Heating</th></tr>
            </thead>
            <tbody id="readings-table"></tbody>
        </table>
    </div>

    <script>
        function createCell(text, className) {
            const td = document.createElement('td');
            td.textContent = text;
            if (className) td.className = className;
            return td;
        }

        function populateGasTable(gas) {
            const tbody = document.getElementById('gas-table');
            tbody.replaceChildren();
            gas.forEach(r => {
                const tr = document.createElement('tr');
                tr.appendChild(createCell(new Date(r.recorded_at).toLocaleString()));
                tr.appendChild(createCell(r.meter_reading));
                tr.appendChild(createCell(r.ccf_since_last || '-'));
                tbody.appendChild(tr);
            });
        }

        function populateReadingsTable(thermostat) {
            const tbody = document.getElementById('readings-table');
            tbody.replaceChildren();
            thermostat.slice(0, 20).forEach(r => {
                const tr = document.createElement('tr');
                tr.appendChild(createCell(new Date(r.recorded_at).toLocaleTimeString()));
                tr.appendChild(createCell(parseFloat(r.indoor_temp).toFixed(1) + '°F'));
                tr.appendChild(createCell(parseFloat(r.outdoor_temp).toFixed(1) + '°F'));
                tr.appendChild(createCell(r.adjusted_outdoor_temp ? parseFloat(r.adjusted_outdoor_temp).toFixed(1) + '°F' : '-'));
                tr.appendChild(createCell(r.is_heating ? 'ON' : 'OFF', r.is_heating ? 'heating-on' : 'heating-off'));
                tbody.appendChild(tr);
            });
        }

        async function loadData() {
            const [thermostat, gas] = await Promise.all([
                fetch('/api/thermostat').then(r => r.json()),
                fetch('/api/gas').then(r => r.json())
            ]);

            // Update current stats
            if (thermostat.length > 0) {
                const latest = thermostat[0];
                document.getElementById('indoor-temp').textContent = parseFloat(latest.indoor_temp).toFixed(1);
                document.getElementById('outdoor-temp').textContent = parseFloat(latest.outdoor_temp).toFixed(1);
                document.getElementById('humidity').textContent = latest.humidity;
                document.getElementById('heating-status').textContent = latest.is_heating ? 'ON' : 'OFF';
                if (latest.is_heating) {
                    document.getElementById('heating-stat').classList.add('heating');
                }
            }

            // Temperature chart
            const tempCtx = document.getElementById('tempChart').getContext('2d');
            new Chart(tempCtx, {
                type: 'line',
                data: {
                    labels: thermostat.map(r => new Date(r.recorded_at)).reverse(),
                    datasets: [
                        {
                            label: 'Indoor',
                            data: thermostat.map(r => parseFloat(r.indoor_temp)).reverse(),
                            borderColor: '#00d4ff',
                            backgroundColor: 'rgba(0, 212, 255, 0.1)',
                            fill: true,
                            tension: 0.3
                        },
                        {
                            label: 'Outdoor',
                            data: thermostat.map(r => parseFloat(r.outdoor_temp)).reverse(),
                            borderColor: '#4ecdc4',
                            backgroundColor: 'rgba(78, 205, 196, 0.1)',
                            fill: true,
                            tension: 0.3
                        },
                        {
                            label: 'Adjusted',
                            data: thermostat.map(r => r.adjusted_outdoor_temp ? parseFloat(r.adjusted_outdoor_temp) : null).reverse(),
                            borderColor: '#ffd93d',
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'hour' },
                            ticks: { color: '#888' },
                            grid: { color: '#333' }
                        },
                        y: {
                            ticks: { color: '#888' },
                            grid: { color: '#333' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#888' } }
                    }
                }
            });

            // Heating chart (show when heating was on)
            const heatingCtx = document.getElementById('heatingChart').getContext('2d');
            new Chart(heatingCtx, {
                type: 'bar',
                data: {
                    labels: thermostat.map(r => new Date(r.recorded_at)).reverse(),
                    datasets: [{
                        label: 'Heating',
                        data: thermostat.map(r => r.is_heating ? 1 : 0).reverse(),
                        backgroundColor: thermostat.map(r => r.is_heating ? '#ff6b6b' : '#333').reverse(),
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'hour' },
                            ticks: { color: '#888' },
                            grid: { color: '#333' }
                        },
                        y: {
                            display: false,
                            max: 1
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });

            // Populate tables using safe DOM methods
            populateGasTable(gas);
            populateReadingsTable(thermostat);
        }

        loadData();
    </script>
</body>
</html>
"""

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/thermostat')
def api_thermostat():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT recorded_at, indoor_temp, outdoor_temp, adjusted_outdoor_temp,
               heat_setpoint, humidity, is_heating
        FROM thermostat_readings
        ORDER BY recorded_at DESC
        LIMIT 100
    """)
    columns = ['recorded_at', 'indoor_temp', 'outdoor_temp', 'adjusted_outdoor_temp',
               'heat_setpoint', 'humidity', 'is_heating']
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    # Convert datetime and decimal to JSON-serializable
    for row in rows:
        row['recorded_at'] = row['recorded_at'].isoformat()
        row['indoor_temp'] = str(row['indoor_temp'])
        row['outdoor_temp'] = str(row['outdoor_temp'])
        row['adjusted_outdoor_temp'] = str(row['adjusted_outdoor_temp']) if row['adjusted_outdoor_temp'] else None

    return jsonify(rows)

@app.route('/api/gas')
def api_gas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT recorded_at, meter_reading, ccf_since_last
        FROM gas_meter_readings
        ORDER BY recorded_at DESC
        LIMIT 20
    """)
    columns = ['recorded_at', 'meter_reading', 'ccf_since_last']
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    for row in rows:
        row['recorded_at'] = row['recorded_at'].isoformat()
        row['ccf_since_last'] = str(row['ccf_since_last']) if row['ccf_since_last'] else None

    return jsonify(rows)

if __name__ == '__main__':
    print("Starting Atmos Dashboard...")
    print("View at: http://localhost:5000")
    app.run(debug=True, port=5000)
