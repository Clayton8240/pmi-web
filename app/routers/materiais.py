from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Material, VolumePorCaixa
from app.routers import templates

router = APIRouter(prefix="/materiais", tags=["materiais"])


@router.get("/")
def lista_materiais(request: Request, db: Session = Depends(get_db)):
    materiais = db.query(Material).filter(Material.ativo == True).order_by(Material.descricao).all()  # noqa
    return templates.TemplateResponse(
        "materiais/lista.html",
        {"request": request, "materiais": materiais, "active_page": "materiais"},
    )


@router.post("/")
def criar_material(
    request: Request,
    part_number: str = Form(...),
    descricao: str = Form(...),
    marca: str = Form(default=""),
    unidade: str = Form(default="UN"),
    db: Session = Depends(get_db),
):
    existente = db.query(Material).filter(Material.part_number.ilike(part_number)).first()
    if existente:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="text-red-600 text-sm p-2">Part number <b>{part_number}</b> já cadastrado.</div>'
            )
        raise HTTPException(status_code=400, detail="Part number já cadastrado")

    mat = Material(
        part_number=part_number.strip().upper(),
        descricao=descricao.strip(),
        marca=marca.strip(),
        unidade=unidade.strip(),
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "materiais/_linha.html", {"request": request, "m": mat}
        )
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/materiais", status_code=303)


@router.delete("/{material_id}", response_class=HTMLResponse)
def deletar_material(material_id: int, db: Session = Depends(get_db)):
    mat = db.get(Material, material_id)
    if mat:
        mat.ativo = False
        db.commit()
    return HTMLResponse("")


# ---------------------------------------------------------------------------
# Volumes por caixa
# ---------------------------------------------------------------------------

@router.post("/{material_id}/volumes")
def adicionar_volume(
    request: Request,
    material_id: int,
    descricao: str = Form(...),
    qtde_por_cx: int = Form(...),
    db: Session = Depends(get_db),
):
    mat = db.get(Material, material_id)
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    vol = VolumePorCaixa(
        material_id=material_id,
        descricao=descricao.strip(),
        qtde_por_cx=qtde_por_cx,
    )
    db.add(vol)
    db.commit()
    db.refresh(vol)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "materiais/_volume_badge.html", {"request": request, "v": vol, "material_id": material_id}
        )
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/materiais", status_code=303)


@router.delete("/{material_id}/volumes/{volume_id}", response_class=HTMLResponse)
def deletar_volume(material_id: int, volume_id: int, db: Session = Depends(get_db)):
    vol = db.get(VolumePorCaixa, volume_id)
    if vol and vol.material_id == material_id:
        db.delete(vol)
        db.commit()
    return HTMLResponse("")
