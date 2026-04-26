from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from backend.governance.metering import RateCardCreate, RateCardUpdate
from backend.persistence.contracts import MeteringLedger
from backend.persistence.governance import PostgresMeteringLedger

logger = logging.getLogger(__name__)


def build_billing_router(
    *,
    metering_ledger: MeteringLedger,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

    @router.get("/rate-cards")
    def list_rate_cards(
        provider: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        cards = metering_ledger.list_rate_cards(provider=provider, status=status)
        return [card.model_dump(mode="json") for card in cards]

    @router.get("/rate-cards/{rate_card_id}")
    def get_rate_card(rate_card_id: str) -> dict:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        card = metering_ledger.get_rate_card(rate_card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="rate_card_not_found")
        return card.model_dump(mode="json")

    @router.post("/rate-cards", status_code=status.HTTP_201_CREATED)
    def create_rate_card(data: RateCardCreate) -> dict:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        card = metering_ledger.create_rate_card(data)
        return card.model_dump(mode="json")

    @router.patch("/rate-cards/{rate_card_id}")
    def update_rate_card(rate_card_id: str, data: RateCardUpdate) -> dict:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        card = metering_ledger.update_rate_card(rate_card_id, data)
        if card is None:
            raise HTTPException(status_code=404, detail="rate_card_not_found")
        return card.model_dump(mode="json")

    @router.post("/rate-cards/{rate_card_id}/activate")
    def activate_rate_card(
        rate_card_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> dict:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        card = metering_ledger.activate_rate_card(rate_card_id, activated_by=x_actor)
        if card is None:
            raise HTTPException(status_code=404, detail="rate_card_not_found")
        return card.model_dump(mode="json")

    @router.delete("/rate-cards/{rate_card_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_rate_card(rate_card_id: str) -> Response:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="rate_cards_not_available")
        deleted = metering_ledger.delete_rate_card(rate_card_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="rate_card_not_found")
        return Response(status_code=204)

    @router.post("/reconcile")
    def run_reconciliation(
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        provider: str,
        provider_reported_total_usd: Decimal,
        mode: str = Query("dry_run", regex="^(dry_run|enforce)$"),
    ) -> dict:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="reconciliation_not_available")
        report = metering_ledger.run_reconciliation(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            provider=provider,
            provider_reported_total_usd=provider_reported_total_usd,
            mode=mode,
        )
        result = report.model_dump(mode="json")
        if abs(report.drift_percentage) > 2:
            logger.warning(
                "billing_drift_exceeded",
                extra={
                    "tenant_id": tenant_id,
                    "provider": provider,
                    "drift_percentage": str(report.drift_percentage),
                    "mode": mode,
                },
            )
        return result

    @router.get("/reconciliation-reports")
    def list_reconciliation_reports(
        tenant_id: str | None = None,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="reconciliation_not_available")
        reports = metering_ledger.list_reconciliation_reports(
            tenant_id=tenant_id,
            provider=provider,
            limit=limit,
        )
        return [r.model_dump(mode="json") for r in reports]

    @router.get("/export")
    def export_billing(
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        format: str = "csv",
        version: str = "v1",
    ) -> Response:
        if format not in {"csv", "json"}:
            raise HTTPException(status_code=400, detail="unsupported_export_format")
        if not isinstance(metering_ledger, PostgresMeteringLedger):
            raise HTTPException(status_code=501, detail="export_not_available")

        if format == "csv":
            content = metering_ledger.export(
                type("MeteringExportRequest", (), {
                    "tenant_id": tenant_id,
                    "period_start": period_start,
                    "period_end": period_end,
                    "format": "csv",
                    "schema_version": version,
                })()
            )
            media_type = "text/csv"
        else:
            facts = metering_ledger._facts_for_period(
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
            )
            if version == "v2":
                import json
                content = "\n".join(
                    json.dumps({
                        "schema_version": "v2",
                        "usage": fact.model_dump(mode="json"),
                    })
                    for fact in facts
                )
            else:
                content = "\n".join(fact.model_dump_json() for fact in facts)
            media_type = "application/x-ndjson"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "X-Billing-Export-Version": version,
                "X-Billing-Export-Format": format,
            },
        )

    return router
