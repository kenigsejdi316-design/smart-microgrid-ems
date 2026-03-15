# Microgrid Smart Management Platform

A one-click runnable big-data microgrid management demo project.

## What This Project Includes

- Data preprocessing with Pandas:
  - Missing value cleaning
  - Linear interpolation fill
  - 3-sigma outlier removal
- Big data simulation for multi-station microgrid telemetry
- Analytics API for overview, trend, hourly mix, and operational alerts
- ECharts dashboard with performance tuning for large datasets

## Quick Start (Windows)

1. Double click `start.bat`
2. Wait for environment setup and dependency installation
3. Open http://127.0.0.1:5000

## Manual Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## API Endpoints

- `GET /api/health`
- `GET /api/stations`
- `GET /api/overview`
- `GET /api/trend?station=ALL&points=3200`
- `GET /api/hourly-mix?station=ALL`
- `GET /api/alerts?station=ALL&limit=12`
- `POST /api/refresh?regenerate=true`

## Project Structure

- `app.py`: Flask app entry
- `microgrid/data_pipeline.py`: synthetic data generation and preprocessing logic
- `microgrid/service.py`: analytics service layer
- `templates/index.html`: dashboard page
- `static/css/styles.css`: UI styling
- `static/js/dashboard.js`: front-end data loading and ECharts rendering
- `start.bat`: one-click startup script

## Notes

- Default dataset size is 180,000 records.
- Charts use ECharts `sampling`, `progressive`, and `dataZoom` for smooth interaction under large data volume.
