from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from app.core.exceptions import ModelNotReadyError
from app.models.domain import ClinicProfile, PredictionResult, RiskDriver
from app.services.model_registry import load_registered_model_artifact

FEATURE_LABELS = {
    "stocked_cabinets": "Licensed Desk seats",
    "active_cabinet_ratio_30d": "Active seat ratio",
    "buyer_count": "Internal product champions",
    "tenure_months": "Clinic tenure",
    "monthly_contract_value": "Monthly recurring revenue",
    "orders_30d": "Recent login activity",
    "order_change_pct": "Usage trend",
    "service_tickets_90d": "Support burden",
    "nps": "Net Promoter Score",
    "days_to_term": "Renewal proximity",
    "invoice_failures_90d": "Payment reliability",
    "stocking_complete": "Onboarding completion",
    "service_ticket_rate": "Ticket frequency",
    "activity_score": "Composite engagement",
    "term_pressure": "Renewal urgency",
    "value_at_risk": "Revenue at risk",
    "segment": "Clinic segment",
    "region": "Region",
}

INTEGER_FEATURES = {
    "stocked_cabinets",
    "buyer_count",
    "tenure_months",
    "orders_30d",
    "service_tickets_90d",
    "nps",
    "days_to_term",
    "invoice_failures_90d",
}


class MLService:
    def __init__(
        self,
        model_path: Path,
        risk_high: float = 0.70,
        risk_medium: float = 0.40,
        *,
        tracking_uri: str = "http://localhost:5000",
        use_model_registry: bool = False,
        registered_model_name: str = "cecilia-clinic-lapse-model",
        deployment_alias: str = "champion",
    ):
        self.model_path = model_path
        self.risk_high = risk_high
        self.risk_medium = risk_medium
        self.tracking_uri = tracking_uri
        self.use_model_registry = use_model_registry
        self.registered_model_name = registered_model_name
        self.deployment_alias = deployment_alias
        self._artifact: dict | None = None

    @property
    def ready(self) -> bool:
        if self.use_model_registry:
            return bool(self.registered_model_name and self.deployment_alias)
        return self.model_path.exists()

    def _load(self) -> dict:
        if self._artifact is None:
            if self.use_model_registry:
                try:
                    artifact, _ = load_registered_model_artifact(
                        tracking_uri=self.tracking_uri,
                        registered_model_name=self.registered_model_name,
                        alias=self.deployment_alias,
                    )
                    self._artifact = artifact
                    return self._artifact
                except Exception as exc:  # noqa: BLE001
                    raise ModelNotReadyError(
                        "Unable to load model from MLflow Model Registry. "
                        f"Model={self.registered_model_name!r}, alias={self.deployment_alias!r}. "
                        f"Details: {exc}"
                    ) from exc
            if not self.model_path.exists():
                raise ModelNotReadyError(
                    f"Model artifact not found at {self.model_path}. Run scripts/bootstrap.py first."
                )
            self._artifact = joblib.load(self.model_path)
        return self._artifact

    def _risk_band(self, probability: float, artifact: dict | None = None) -> str:
        thresholds = (artifact or {}).get("risk_thresholds", {})
        risk_high = float(thresholds.get("high", self.risk_high))
        risk_medium = float(thresholds.get("medium", self.risk_medium))
        if probability >= risk_high:
            return "high"
        if probability >= risk_medium:
            return "medium"
        return "low"

    def predict(self, profile: ClinicProfile, top_n: int = 5) -> PredictionResult:
        artifact = self._load()
        frame = pd.DataFrame([profile.model_dump()])
        features = artifact["features"]
        probability = float(artifact["pipeline"].predict_proba(frame[features])[:, 1][0])
        drivers = self._counterfactual_drivers(frame, probability, artifact, top_n)
        return PredictionResult(
            clinic_id=profile.clinic_id,
            lapse_probability=probability,
            risk_band=self._risk_band(probability, artifact),
            top_drivers=drivers,
            model_version=artifact["model_version"],
        )


    def score_many(self, profiles: list[ClinicProfile]) -> list[tuple[str, float, str]]:
        """Vectorized scoring used by batch ranking and golden-dataset construction."""
        if not profiles:
            return []
        artifact = self._load()
        frame = pd.DataFrame([profile.model_dump() for profile in profiles])
        probabilities = artifact["pipeline"].predict_proba(frame[artifact["features"]])[:, 1]
        return [
            (profile.clinic_id, float(probability), self._risk_band(float(probability), artifact))
            for profile, probability in zip(profiles, probabilities, strict=True)
        ]

    def _counterfactual_drivers(
        self, frame: pd.DataFrame, actual_probability: float, artifact: dict, top_n: int
    ) -> list[RiskDriver]:
        pipeline = artifact["pipeline"]
        baselines = artifact["baselines"]
        impacts: list[RiskDriver] = []
        for feature in artifact["features"]:
            counterfactual = frame.copy()
            replacement = baselines[feature]
            if feature == "stocking_complete":
                replacement = bool(round(float(replacement)))
            elif feature in INTEGER_FEATURES:
                replacement = int(round(float(replacement)))
            counterfactual.loc[0, feature] = replacement
            baseline_probability = float(
                pipeline.predict_proba(counterfactual[artifact["features"]])[:, 1][0]
            )
            impact = actual_probability - baseline_probability
            value = frame.loc[0, feature]
            if hasattr(value, "item"):
                value = value.item()
            baseline = baselines[feature]
            direction = "risk" if impact >= 0 else "protective"
            impacts.append(
                RiskDriver(
                    feature=feature,
                    clinic_value=value,
                    baseline_value=baseline,
                    probability_impact=float(impact),
                    direction=direction,
                    explanation=(
                        f"{FEATURE_LABELS.get(feature, feature)} changes estimated lapse risk by "
                        f"{impact:+.1%} versus the training-data baseline."
                    ),
                )
            )
        impacts.sort(key=lambda item: abs(item.probability_impact), reverse=True)
        return impacts[:top_n]
