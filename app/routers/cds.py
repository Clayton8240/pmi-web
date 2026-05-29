from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CD, ItemCD
from app.routers import templates
from app.services.volume_calc import calcular_volume_cd

router = APIRouter(prefix="/cds", tags=["cds"])


@router.get("/")
def lista_cds(
    request: Request,
    db: Session = Depends(get_db),
    q: str = Query(default=""),
):
    query = db.query(CD).filter(CD.ativo == True)  # noqa: E712
    if q:
        query = query.filter(
            CD.regional.ilike(f"%{q}%") |
            CD.cidade.ilike(f"%{q}%") |
            CD.filial.ilike(f"%{q}%") |
            CD.descricao_pacote.ilike(f"%{q}%")
        )
    cds = query.order_by(CD.id).all()

    # Se for requisição HTMX, retorna apenas a tabela
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "cds/_tabela.html", {"cds": cds, "q": q}
        )
    return templates.TemplateResponse(
        request,
        "cds/lista.html", {"cds": cds, "q": q, "active_page": "cds"}
    )


@router.get("/{cd_id}")
def detalhe_cd(request: Request, cd_id: int, db: Session = Depends(get_db)):
    cd = db.get(CD, cd_id)
    if not cd:
        return templates.TemplateResponse(
            request,
            "cds/lista.html",
            {"cds": [], "q": "", "active_page": "cds", "erro": "CD não encontrado"},
        )
    itens = db.query(ItemCD).filter(ItemCD.cd_id == cd_id).all()
    volume_info = calcular_volume_cd(cd_id, db)
    return templates.TemplateResponse(
        request,
        "cds/detalhe.html",
        {"cd": cd, "itens": itens, "volume_info": volume_info, "active_page": "cds"},
    )
