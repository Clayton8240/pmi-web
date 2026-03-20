"""Endpoints de API chamados pelo HTMX para buscar dados dinamicamente."""

from fastapi import APIRouter, Depends, Request, Query as QueryParam
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CD, ItemCD
from app.routers import templates
from app.services.volume_calc import calcular_volume_cd, proximo_num_caixa
from app.config import TRANSPORTADORA_PADRAO

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/cds/buscar")
def buscar_cd(
    request: Request,
    ctrl_id: str = "",
    campanha_id: int | None = QueryParam(default=None),
    db: Session = Depends(get_db),
):
    """HTMX: retorna partial HTML com dados do CD e volumes calculados."""
    if not ctrl_id or not ctrl_id.strip().isdigit():
        return HTMLResponse(
            '<p class="text-yellow-600 text-sm">⚠️ Informe um número válido.</p>'
        )

    cd_id = int(ctrl_id.strip())
    cd = db.get(CD, cd_id)
    if not cd:
        return HTMLResponse(
            f'<p class="text-red-600 text-sm">❌ CD <b>{cd_id}</b> não encontrado no banco.</p>'
        )

    itens = db.query(ItemCD).filter(ItemCD.cd_id == cd_id).all()
    volume_info = calcular_volume_cd(cd_id, db, campanha_id)
    prox_caixa = proximo_num_caixa(db, campanha_id)

    return templates.TemplateResponse(
        "partials/cd_info.html",
        {
            "request": request,
            "cd": cd,
            "itens": itens,
            "volume_info": volume_info,
            "prox_caixa": prox_caixa,
            "transportador_padrao": TRANSPORTADORA_PADRAO,
        },
    )
