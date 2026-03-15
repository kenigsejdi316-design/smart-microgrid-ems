from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

NUMERIC_COLUMNS = ["pv_kw", "wind_kw", "load_kw", "battery_soc", "grid_price"]


@dataclass(frozen=True)
class PreprocessReport:
    total_rows: int
    missing_before: int
    missing_after: int
    interpolated_cells: int
    outliers_removed: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "missing_before": self.missing_before,
            "missing_after": self.missing_after,
            "interpolated_cells": self.interpolated_cells,
            "outliers_removed": self.outliers_removed,
        }


def generate_synthetic_data(rows: int = 120_000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic multi-station microgrid telemetry with noise, missing values and outliers."""
    rng = np.random.default_rng(seed)
    station_ids = ["MG-01", "MG-02", "MG-03", "MG-04"]
    points_per_station = max(rows // len(station_ids), 2_000)
    start_time = pd.Timestamp("2026-01-01 00:00:00")

    frames = []
    for idx, station_id in enumerate(station_ids):
        t = np.arange(points_per_station)
        day_phase = (t % 288) / 288.0
        station_factor = 0.88 + idx * 0.09

        pv_base = np.maximum(0.0, np.sin(np.pi * day_phase))
        pv_kw = (165 * pv_base + rng.normal(8, 6, points_per_station)) * station_factor

        wind_kw = (
            rng.normal(95, 22, points_per_station)
            + 24 * np.sin(2 * np.pi * day_phase + idx * 0.4)
            + rng.normal(0, 6, points_per_station)
        ) * station_factor

        load_kw = (
            205
            + 34 * np.sin(2 * np.pi * day_phase - 0.75)
            + 28 * np.sin(4 * np.pi * day_phase + idx * 0.3)
            + rng.normal(0, 12, points_per_station)
        ) * (0.95 + idx * 0.06)

        battery_soc = 54 + 20 * np.sin(2 * np.pi * day_phase + idx * 0.5) + rng.normal(0, 4, points_per_station)
        grid_price = 0.58 + 0.12 * np.sin(2 * np.pi * day_phase + 0.4) + rng.normal(0, 0.02, points_per_station)

        frame = pd.DataFrame(
            {
                "timestamp": start_time + pd.to_timedelta(t * 5, unit="m"),
                "station_id": station_id,
                "pv_kw": np.clip(pv_kw, 0, None),
                "wind_kw": np.clip(wind_kw, 0, None),
                "load_kw": np.clip(load_kw, 1, None),
                "battery_soc": np.clip(battery_soc, 5, 99),
                "grid_price": np.clip(grid_price, 0.1, None),
            }
        )
        frames.append(frame)

    dataset = pd.concat(frames, ignore_index=True)

    for col in NUMERIC_COLUMNS:
        missing_mask = rng.random(len(dataset)) < 0.024
        dataset.loc[missing_mask, col] = np.nan

    high_outlier_mask = rng.random(len(dataset)) < 0.005
    low_outlier_mask = rng.random(len(dataset)) < 0.003

    for col in ["pv_kw", "wind_kw", "load_kw"]:
        dataset.loc[high_outlier_mask, col] = dataset.loc[high_outlier_mask, col] * rng.uniform(3.6, 5.2)
        dataset.loc[low_outlier_mask, col] = dataset.loc[low_outlier_mask, col] * rng.uniform(0.02, 0.1)

    dataset.loc[high_outlier_mask, "battery_soc"] = dataset.loc[high_outlier_mask, "battery_soc"] + rng.uniform(60, 110)
    dataset.loc[low_outlier_mask, "battery_soc"] = dataset.loc[low_outlier_mask, "battery_soc"] - rng.uniform(40, 70)

    dataset.loc[high_outlier_mask, "grid_price"] = dataset.loc[high_outlier_mask, "grid_price"] * rng.uniform(2.2, 3.0)

    dataset = dataset.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return dataset


def _three_sigma_mask(series: pd.Series) -> pd.Series:
    mean = series.mean()
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(False, index=series.index)
    return (series - mean).abs() > (3 * std)


def preprocess_data(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, PreprocessReport]:
    """Apply linear interpolation and 3-sigma outlier removal by station."""
    df = raw_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "station_id"]).sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    missing_before = int(df[NUMERIC_COLUMNS].isna().sum().sum())

    for col in NUMERIC_COLUMNS:
        df[col] = df.groupby("station_id")[col].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both")
        )

    outlier_count = 0
    for col in NUMERIC_COLUMNS:
        outlier_mask = (
            df.groupby("station_id")[col]
            .apply(_three_sigma_mask)
            .reset_index(level=0, drop=True)
        )
        outlier_count += int(outlier_mask.sum())
        df.loc[outlier_mask, col] = np.nan

    for col in NUMERIC_COLUMNS:
        df[col] = df.groupby("station_id")[col].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both")
        )

    df["pv_kw"] = df["pv_kw"].clip(lower=0)
    df["wind_kw"] = df["wind_kw"].clip(lower=0)
    df["load_kw"] = df["load_kw"].clip(lower=0)
    df["battery_soc"] = df["battery_soc"].clip(lower=0, upper=100)
    df["grid_price"] = df["grid_price"].clip(lower=0)

    missing_after = int(df[NUMERIC_COLUMNS].isna().sum().sum())
    interpolated_cells = int((missing_before + outlier_count) - missing_after)

    report = PreprocessReport(
        total_rows=int(len(df)),
        missing_before=missing_before,
        missing_after=missing_after,
        interpolated_cells=interpolated_cells,
        outliers_removed=outlier_count,
    )
    return df, report


def load_or_generate_raw_dataset(
    raw_csv_path: Path,
    rows: int,
    regenerate: bool = False,
    seed: int = 42,
) -> pd.DataFrame:
    raw_csv_path.parent.mkdir(parents=True, exist_ok=True)

    if raw_csv_path.exists() and not regenerate:
        return pd.read_csv(raw_csv_path, parse_dates=["timestamp"])

    raw_df = generate_synthetic_data(rows=rows, seed=seed)
    raw_df.to_csv(raw_csv_path, index=False)
    return raw_df


def build_clean_dataset(
    raw_csv_path: Path,
    rows: int,
    regenerate_raw: bool = False,
    seed: int = 42,
) -> Tuple[pd.DataFrame, PreprocessReport]:
    raw_df = load_or_generate_raw_dataset(raw_csv_path=raw_csv_path, rows=rows, regenerate=regenerate_raw, seed=seed)
    clean_df, report = preprocess_data(raw_df)
    return clean_df, report
