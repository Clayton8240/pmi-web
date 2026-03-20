import os
import tempfile
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers import templates
from app.services.importacao import importar_cds_excel
from app.models import Campanha

router = APIRouter(prefix="/importacao", tags=["importacao"])


@router.get("/")
def pagina_importacao(request: Request, db: Session = Depends(get_db)):
    from app.models import CD, ItemCD, Material
    stats = {
        "total_cds": db.query(CD).count(),
        "total_itens": db.query(ItemCD).count(),
        "total_materiais": db.query(Material).count(),
    }
    campanhas = db.query(Campanha).order_by(Campanha.criada_em.desc()).all()
    return templates.TemplateResponse(
        "importacao/index.html",
        {
            "request": request,
            "stats": stats,
            "active_page": "importacao",
            "campanhas": campanhas,
        },
    )


@router.post("/cds")
async def importar_cds(
    request: Request,
    arquivo: UploadFile = File(...),
    nome_campanha: str = Form(""),
    db: Session = Depends(get_db),
):
    suffix = os.path.splitext(arquivo.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        conteudo = await arquivo.read()
        tmp.write(conteudo)
        tmp_path = tmp.name

    try:
        resultado = importar_cds_excel(
            tmp_path, db,
            nome_campanha=nome_campanha.strip() or None,
        )
    finally:
        os.unlink(tmp_path)

    if "erro" in resultado:
        msg = f'<div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">❌ {resultado["erro"]}</div>'
    else:
        campanha_id = resultado["campanha_id"]
        campanha_nome = resultado["campanha_nome"]
        msg = f"""
        <div class="bg-green-50 border border-green-200 text-green-700 rounded-lg p-4">
          <p class="font-semibold">✅ Importação concluída! Campanha criada: <b>{campanha_nome}</b></p>
          <ul class="text-sm mt-2 space-y-1">
            <li>CDs inseridos: <b>{resultado['cds_inseridos']}</b></li>
            <li>CDs atualizados: <b>{resultado['cds_atualizados']}</b></li>
            <li>Itens importados: <b>{resultado['itens_inseridos']}</b></li>
          </ul>
          <p class="text-xs mt-3">
            <a href="/etiquetas/lote?campanha_id={campanha_id}" class="underline font-medium">
              → Ir para Gerar Lote desta campanha
            </a>
          </p>
        </div>
        """
    return HTMLResponse(msg)

