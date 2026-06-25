from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import enforce_lan_and_key
from app.config import get_settings
from app.schemas import JobResponse, PrintJobRequest, CoffeeLabelData
from app.state import get_print_queue, get_store

router = APIRouter(dependencies=[Depends(enforce_lan_and_key)])


@router.post("/admin/test-print", response_model=JobResponse, status_code=202)
def test_print(client_ip: str = Depends(enforce_lan_and_key)) -> JobResponse:
    settings = get_settings()
    store = get_store()

    template_name = settings.enabled_templates[0] if settings.enabled_templates else "house-of-coffee-62mm"
    payload = PrintJobRequest(
        template=template_name,
        job_ref=f"diagnostic-test-print",
        data=CoffeeLabelData(
            product_name="TEST LABEL - HOUSE OF COFFEE",
            grind="Test Grind",
            weight="0.000 kg",
            strength="0",
            flavour="0",
            roast="0",
            best_before="00.00.0000",
        ),
    )

    job_id = store.create_job(
        template=payload.template,
        payload=payload.model_dump(),
        copies=1,
        job_ref=None,  # always print, never deduped
        submitted_by_ip=client_ip,
    )
    get_print_queue().enqueue(job_id)
    return JobResponse.model_validate(store.get_job(job_id))
