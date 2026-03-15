from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .data_pipeline import build_clean_dataset


class DataService:
    def __init__(self, raw_path: Path, rows: int = 120_000) -> None:
        self.raw_path = raw_path
        self.rows = rows
        self.clean_df = pd.DataFrame()
        self.report: Dict[str, Any] = {}
        self.last_refresh: datetime | None = None

    def refresh(self, regenerate_raw: bool = False) -> Dict[str, Any]:
        clean_df, report = build_clean_dataset(
            raw_csv_path=self.raw_path,
            rows=self.rows,
            regenerate_raw=regenerate_raw,
        )
        self.clean_df = clean_df
        self.report = asdict(report)
        self.last_refresh = datetime.now()
        return {
            "updated_at": self.last_refresh.isoformat(timespec="seconds"),
            "rows": int(len(self.clean_df)),
            "preprocess": self.report,
        }

    def _ensure_data(self) -> None:
        if self.clean_df.empty:
            self.refresh(regenerate_raw=False)

    @staticmethod
    def _downsample(df: pd.DataFrame, max_points: int) -> pd.DataFrame:
        if max_points <= 0 or len(df) <= max_points:
            return df
        step = int(np.ceil(len(df) / max_points))
        return df.iloc[::step].reset_index(drop=True)

    def stations(self) -> List[str]:
        self._ensure_data()
        station_list = sorted(self.clean_df["station_id"].dropna().unique().tolist())
        return ["ALL", *station_list]

    def overview(self) -> Dict[str, Any]:
        self._ensure_data()
        df = self.clean_df.copy()
        df["generation_kw"] = df["pv_kw"] + df["wind_kw"]

        latest_time = df["timestamp"].max()
        window_df = df[df["timestamp"] >= (latest_time - pd.Timedelta(hours=24))].copy()

        generation_sum = float(window_df["generation_kw"].sum())
        load_sum = float(window_df["load_kw"].sum())
        renewable_ratio = float((generation_sum / max(load_sum, 1e-6)) * 100)

        grid_import_kw = np.maximum(window_df["load_kw"] - window_df["generation_kw"], 0)
        estimated_cost = float((grid_import_kw * window_df["grid_price"]).sum() / 12)
        carbon_reduction = float((window_df["generation_kw"].sum() / 12) * 0.72)

        latest_station = (
            df.sort_values("timestamp")
            .groupby("station_id", as_index=False)
            .tail(1)
            .sort_values("station_id")
        )

        station_cards = []
        for _, row in latest_station.iterrows():
            generation_kw = float(row["generation_kw"])
            load_kw = float(row["load_kw"])
            station_cards.append(
                {
                    "station_id": row["station_id"],
                    "generation_kw": generation_kw,
                    "load_kw": load_kw,
                    "battery_soc": float(row["battery_soc"]),
                    "power_gap_kw": float(generation_kw - load_kw),
                }
            )

        return {
            "updated_at": self.last_refresh.isoformat(timespec="seconds") if self.last_refresh else "",
            "data_points": int(len(df)),
            "renewable_ratio": renewable_ratio,
            "avg_soc": float(window_df["battery_soc"].mean()),
            "estimated_cost": estimated_cost,
            "carbon_reduction_kg": carbon_reduction,
            "station_cards": station_cards,
            "preprocess": self.report,
        }

    def trend(self, station_id: str = "ALL", points: int = 2_400) -> Dict[str, Any]:
        self._ensure_data()

        working_df = self.clean_df if station_id == "ALL" else self.clean_df[self.clean_df["station_id"] == station_id]
        if working_df.empty:
            working_df = self.clean_df
            station_id = "ALL"

        trend_df = working_df.sort_values("timestamp").copy()
        trend_df["generation_kw"] = trend_df["pv_kw"] + trend_df["wind_kw"]
        trend_df = self._downsample(trend_df, points)

        return {
            "station_id": station_id,
            "timestamps": trend_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            "pv_kw": np.round(trend_df["pv_kw"], 3).tolist(),
            "wind_kw": np.round(trend_df["wind_kw"], 3).tolist(),
            "load_kw": np.round(trend_df["load_kw"], 3).tolist(),
            "generation_kw": np.round(trend_df["generation_kw"], 3).tolist(),
            "battery_soc": np.round(trend_df["battery_soc"], 3).tolist(),
        }

    def hourly_mix(self, station_id: str = "ALL") -> Dict[str, Any]:
        self._ensure_data()

        working_df = self.clean_df if station_id == "ALL" else self.clean_df[self.clean_df["station_id"] == station_id]
        if working_df.empty:
            working_df = self.clean_df
            station_id = "ALL"

        recent = working_df[working_df["timestamp"] >= (working_df["timestamp"].max() - pd.Timedelta(hours=48))].copy()

        hourly = (
            recent.set_index("timestamp")[["pv_kw", "wind_kw", "load_kw"]]
            .resample("1h")
            .mean()
            .dropna()
            .reset_index()
        )

        return {
            "station_id": station_id,
            "hours": hourly["timestamp"].dt.strftime("%m-%d %H:%M").tolist(),
            "pv_kw": np.round(hourly["pv_kw"], 3).tolist(),
            "wind_kw": np.round(hourly["wind_kw"], 3).tolist(),
            "load_kw": np.round(hourly["load_kw"], 3).tolist(),
        }

    def alerts(self, station_id: str = "ALL", limit: int = 12) -> List[Dict[str, Any]]:
        self._ensure_data()

        working_df = self.clean_df if station_id == "ALL" else self.clean_df[self.clean_df["station_id"] == station_id]
        if working_df.empty:
            working_df = self.clean_df

        df = working_df.copy()
        df["generation_kw"] = df["pv_kw"] + df["wind_kw"]

        high_price_threshold = float(df["grid_price"].quantile(0.95))
        stress_mask = (
            (df["load_kw"] > (df["generation_kw"] * 1.22))
            | (df["battery_soc"] < 18)
            | (df["grid_price"] > high_price_threshold)
        )

        alert_df = (
            df.loc[
                stress_mask,
                ["timestamp", "station_id", "load_kw", "generation_kw", "battery_soc", "grid_price"],
            ]
            .sort_values("timestamp", ascending=False)
            .head(limit)
        )

        payload: List[Dict[str, Any]] = []
        for _, row in alert_df.iterrows():
            reasons = []
            if row["load_kw"] > row["generation_kw"] * 1.22:
                reasons.append("high_load")
            if row["battery_soc"] < 18:
                reasons.append("low_soc")
            if row["grid_price"] > high_price_threshold:
                reasons.append("peak_price")

            payload.append(
                {
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                    "station_id": row["station_id"],
                    "load_kw": float(row["load_kw"]),
                    "generation_kw": float(row["generation_kw"]),
                    "battery_soc": float(row["battery_soc"]),
                    "grid_price": float(row["grid_price"]),
                    "reasons": reasons,
                }
            )

        return payload
