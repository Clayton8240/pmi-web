from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
from app.database import get_db
from app.models import CD, ItemCD, Etiqueta, ItemEtiqueta, Campanha, Material, VolumePorCaixa
from app.routers import templates
from app.services.volume_calc import (
    proximo_num_caixa,
    materiais_pendentes_capacidade,
    montar_pacotes_cd,
    _bulk_capacidades,
)
from app.services.pdf_service import PDFService
from app.config import OUTPUT_FOLDER, TRANSPORTADORA_PADRAO

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])
pdf_svc = PDFService()


def _limpar_lotes_antigos(dias: int = 30) -> None:
    """Remove arquivos LOTE_*.pdf com mais de `dias` dias da pasta de saída."""
    limite = datetime.now() - timedelta(days=dias)
    try:
        for nome in os.listdir(OUTPUT_FOLDER):
            if not nome.startswith("LOTE_") or not nome.endswith(".pdf"):
                continue
            caminho = os.path.join(OUTPUT_FOLDER, nome)
            mtime = datetime.fromtimestamp(os.path.getmtime(caminho))
            if mtime < limite:
                os.remove(caminho)
    except OSError:
        pass


def _campanha_ativa(db: Session) -> Campanha | None:
    return db.query(Campanha).filter(Campanha.status == "ativa").order_by(Campanha.criada_em.desc()).first()


# ---------------------------------------------------------------------------
# Gerar Lote (todas as etiquetas da campanha de uma vez)
# ---------------------------------------------------------------------------

@router.get("/lote")
def pagina_lote(
    request: Request,
    campanha_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    campanha = db.get(Campanha, campanha_id) if campanha_id else _campanha_ativa(db)
    campanhas = db.query(Campanha).order_by(Campanha.criada_em.desc()).all()

    pendentes_cap: list = []
    cds_info = []
    total_caixas = 0
    if campanha:
        pendentes_cap = materiais_pendentes_capacidade(db, campanha.id)

        cds_ids = db.query(ItemCD.cd_id).filter(
            ItemCD.campanha_id == campanha.id
        ).distinct().all()
        cds_ids = [r[0] for r in cds_ids]
        for cd_id in cds_ids:
            cd = db.get(CD, cd_id)
            if not cd or not cd.ativo:
                continue
            num_itens = db.query(ItemCD).filter(
                ItemCD.cd_id == cd_id,
                ItemCD.campanha_id == campanha.id,
            ).count()
            if pendentes_cap:
                # Sem capacidades ainda — não dá para calcular pacotes
                num_pacotes = 0
            else:
                num_pacotes = len(montar_pacotes_cd(cd_id, db, campanha.id))
            total_caixas += num_pacotes
            cds_info.append({
                "cd": cd,
                "num_itens": num_itens,
                "num_caixas": num_pacotes,
                "volume_texto": "",
            })

    prox_caixa = proximo_num_caixa(db, campanha.id if campanha else None)
    return templates.TemplateResponse(
        request,
        "etiquetas/lote.html",
        {
            "active_page": "lote",
            "campanha": campanha,
            "campanhas": campanhas,
            "cds_info": cds_info,
            "total_caixas": total_caixas,
            "prox_caixa": prox_caixa,
            "transportador_padrao": TRANSPORTADORA_PADRAO,
            "pendentes_cap": pendentes_cap,
        },
    )


@router.post("/lote/capacidades")
async def salvar_capacidades(
    request: Request,
    db: Session = Depends(get_db),
):
    """Recebe a quantidade máxima por pacote informada pelo usuário para
    cada material pendente da campanha. Campos no form: `cap_<material_id>`,
    mais `campanha_id` para o redirect."""
    data = await request.form()
    campanha_id = int(data.get("campanha_id") or 0)
    for key, value in data.items():
        if not key.startswith("cap_"):
            continue
        try:
            mat_id = int(key.split("_", 1)[1])
            qtde = int(value)
        except (ValueError, TypeError):
            continue
        if qtde <= 0:
            continue
        mat = db.get(Material, mat_id)
        if not mat:
            continue
        db.query(VolumePorCaixa).filter(
            VolumePorCaixa.material_id == mat_id,
            VolumePorCaixa.ativo == True,  # noqa: E712
        ).update({"ativo": False})
        db.add(VolumePorCaixa(
            material_id=mat_id,
            descricao=f"{qtde}UN/CX",
            qtde_por_cx=qtde,
            ativo=True,
        ))
    db.commit()
    suffix = f"?campanha_id={campanha_id}" if campanha_id else ""
    return RedirectResponse(url=f"/etiquetas/lote{suffix}", status_code=303)


@router.post("/lote")
def gerar_lote(
    request: Request,
    campanha_id: int = Form(...),
    embalagem: str = Form(default=""),
    projeto: str = Form(default=""),
    transportador: str = Form(default=""),
    db: Session = Depends(get_db),
):
    campanha = db.get(Campanha, campanha_id)
    if not campanha:
        return HTMLResponse('<p class="text-red-600">Campanha não encontrada.</p>')

    pendentes = materiais_pendentes_capacidade(db, campanha_id)
    if pendentes:
        nomes = ", ".join(p["part_number"] for p in pendentes[:5])
        extra = f" (+{len(pendentes) - 5})" if len(pendentes) > 5 else ""
        return HTMLResponse(
            f'<p class="text-red-600">Defina a quantidade máxima por pacote para os materiais: '
            f'{nomes}{extra}. Recarregue a página.</p>'
        )

    transp = transportador.strip() or TRANSPORTADORA_PADRAO
    hoje = datetime.now().strftime("%d/%m/%Y")
    import time, logging
    logger = logging.getLogger("pmi-web.gerar_lote")
    t0 = time.monotonic()

    cds_ids = db.query(ItemCD.cd_id).filter(
        ItemCD.campanha_id == campanha_id
    ).distinct().order_by(ItemCD.cd_id).all()
    cds_ids = [r[0] for r in cds_ids]

    # Pré-carrega tudo em bulk para evitar N+1
    cap_cache = _bulk_capacidades(db)
    cds_map = {c.id: c for c in db.query(CD).filter(CD.id.in_(cds_ids)).all()}
    itens_all = (
        db.query(ItemCD)
        .filter(ItemCD.campanha_id == campanha_id)
        .order_by(ItemCD.cd_id, ItemCD.id)
        .all()
    )
    itens_por_cd: dict[int, list] = {}
    for it in itens_all:
        itens_por_cd.setdefault(it.cd_id, []).append(it)
    logger.warning("LOTE t1=%.2fs (carregou %d cds, %d itens)",
                   time.monotonic() - t0, len(cds_ids), len(itens_all))

    lote_para_pdf: list = []
    etiquetas_geradas: list = []
    # Buffer para inserção em lote (muito mais rápido que add+flush por iteração)
    etiqueta_rows: list[dict] = []
    item_rows_por_etiqueta_idx: list[list[dict]] = []
    info_por_etiqueta: list[dict] = []  # cd, dados_pdf, pkg_itens
    contador_caixa = 1

    for cd_id in cds_ids:
        cd = cds_map.get(cd_id)
        if not cd:
            continue
        pacotes = montar_pacotes_cd(
            cd_id, db, campanha_id,
            cap_cache=cap_cache,
            itens=itens_por_cd.get(cd_id, []),
        )
        num_caixas = len(pacotes)
        if num_caixas == 0:
            continue

        for idx, pkg_itens in enumerate(pacotes):
            prox = contador_caixa
            contador_caixa += 1
            volume_str = f"{idx + 1}/{num_caixas}"

            dados_pdf = {
                "num_caixa": prox,
                "cd_id": cd_id,
                "cnpj": cd.cnpj or "",
                "regional": cd.regional or "",
                "filial": cd.filial or "",
                "cidade": cd.cidade or "",
                "uf": cd.uf or "",
                "zona_venda": cd.zona_venda or "",
                "volume": volume_str,
                "embalagem": embalagem,
                "projeto": projeto or campanha.nome,
                "transportador": transp,
                "data": hoje,
            }

            etiqueta_rows.append({
                "cd_id": cd_id,
                "campanha_id": campanha_id,
                "num_caixa": prox,
                "volume": volume_str,
                "embalagem": embalagem,
                "projeto": projeto or campanha.nome,
                "transportador": transp,
                "pdf_path": None,
            })
            item_rows_por_etiqueta_idx.append([
                {
                    "part_number": it["part_number"],
                    "marca": it["marca"],
                    "descricao": it["descricao"],
                    "qtde": it["qtde"],
                }
                for it in pkg_itens
            ])
            info_por_etiqueta.append({
                "cd": cd, "dados_pdf": dados_pdf, "pkg_itens": pkg_itens,
                "num_caixa": prox, "volume": volume_str,
            })

    logger.warning("LOTE t2=%.2fs (montou %d etiquetas em memória)",
                   time.monotonic() - t0, len(etiqueta_rows))

    # Bulk insert das etiquetas, depois recupera IDs por num_caixa para esta campanha
    if etiqueta_rows:
        db.bulk_insert_mappings(Etiqueta, etiqueta_rows)
        db.flush()
        # mapeia num_caixa -> id (campanha_id é único por num_caixa nesta sessão)
        id_por_caixa = dict(
            db.query(Etiqueta.num_caixa, Etiqueta.id)
            .filter(Etiqueta.campanha_id == campanha_id)
            .all()
        )
        # monta linhas de itens com etiqueta_id resolvido
        all_item_rows: list[dict] = []
        for idx, rows in enumerate(item_rows_por_etiqueta_idx):
            num_caixa = etiqueta_rows[idx]["num_caixa"]
            eid = id_por_caixa.get(num_caixa)
            if eid is None:
                continue
            for r in rows:
                r2 = dict(r)
                r2["etiqueta_id"] = eid
                all_item_rows.append(r2)
        if all_item_rows:
            db.bulk_insert_mappings(ItemEtiqueta, all_item_rows)

        # popula etiquetas_geradas para o template
        for idx, info in enumerate(info_por_etiqueta):
            num_caixa = etiqueta_rows[idx]["num_caixa"]
            lote_para_pdf.append({"dados": info["dados_pdf"], "itens": info["pkg_itens"]})
            etiquetas_geradas.append({
                "id": id_por_caixa.get(num_caixa, 0),
                "num_caixa": num_caixa,
                "cd_id": info["cd"].id,
                "cd_cidade": info["cd"].cidade or "",
                "cd_uf": info["cd"].uf or "",
                "volume": info["volume"],
            })

    db.commit()
    logger.warning("LOTE t3=%.2fs (commit db ok)", time.monotonic() - t0)

    # Limpa PDFs de lote com mais de 30 dias
    _limpar_lotes_antigos()

    pdf_lote_filename = ""
    if lote_para_pdf:
        pdf_lote_path = pdf_svc.gerar_lote_paralelo(lote_para_pdf, workers=4)
        pdf_lote_filename = os.path.basename(pdf_lote_path)
    logger.warning("LOTE t4=%.2fs (pdf gerado: %s)",
                   time.monotonic() - t0, pdf_lote_filename)

    return templates.TemplateResponse(
        request,
        "etiquetas/_sucesso_lote.html",
        {
            "etiquetas": etiquetas_geradas,
            "pdf_lote_filename": pdf_lote_filename,
            "total": len(etiquetas_geradas),
            "campanha_nome": campanha.nome,
        },
    )


@router.get("/lote/pdf/{filename}")
def download_pdf_lote(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        return HTMLResponse("Arquivo inválido.", status_code=400)
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return HTMLResponse("PDF não encontrado.", status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.get("/lote/imprimir/{filename}")
def imprimir_pdf_lote(filename: str):
    """Página de impressão: abre o PDF unificado e dispara o diálogo de impressão."""
    if "/" in filename or "\\" in filename or ".." in filename:
        return HTMLResponse("Arquivo inválido.", status_code=400)
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return HTMLResponse("PDF não encontrado.", status_code=404)
    pdf_url = f"/etiquetas/lote/pdf/{filename}"
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Imprimir Etiquetas PMI</title>
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; background: #f5f5f5; }}
    iframe {{ position: fixed; inset: 0; width: 100%; height: 100%; border: none; }}
    #aviso {{
      position: fixed; top: 1rem; left: 50%; transform: translateX(-50%);
      background: #fff; border: 1px solid #d1d5db; border-radius: 8px;
      padding: 0.75rem 1.5rem; font-family: sans-serif; font-size: 13px;
      color: #374151; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10;
      display: flex; align-items: center; gap: 0.5rem;
    }}
    #aviso span {{ animation: pulsar 1s infinite alternate; }}
    @keyframes pulsar {{ from {{ opacity: 1; }} to {{ opacity: 0.4; }} }}
  </style>
</head>
<body>
  <div id="aviso">
    <span>⏳</span> Aguarde — abrindo diálogo de impressão…
    <small style="color:#9ca3af; margin-left:0.5rem">Se não abrir, use Ctrl+P</small>
  </div>
  <iframe id="pdf-frame" src="{pdf_url}"
          onload="document.getElementById('aviso').style.display='none';
                  try {{ this.contentWindow.print(); }} catch(e) {{ window.print(); }}">
  </iframe>
</body>
</html>"""
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Reimpressão de etiqueta individual
# ---------------------------------------------------------------------------

@router.post("/{etiqueta_id}/reimprimir")
def reimprimir(etiqueta_id: int, db: Session = Depends(get_db)):
    original = db.get(Etiqueta, etiqueta_id)
    if not original:
        return HTMLResponse("Etiqueta não encontrada.", status_code=404)

    itens_originais = db.query(ItemEtiqueta).filter(ItemEtiqueta.etiqueta_id == etiqueta_id).all()
    itens_dict = [
        {"part_number": it.part_number, "marca": it.marca, "descricao": it.descricao, "qtde": it.qtde}
        for it in itens_originais
    ]

    reimp = Etiqueta(
        cd_id=original.cd_id,
        campanha_id=original.campanha_id,
        num_caixa=original.num_caixa,
        volume=original.volume,
        embalagem=original.embalagem,
        projeto=original.projeto,
        transportador=original.transportador,
        pdf_path=None,
        reimpressao=True,
    )
    db.add(reimp)
    db.flush()
    for it in itens_dict:
        db.add(ItemEtiqueta(
            etiqueta_id=reimp.id,
            part_number=it["part_number"],
            marca=it["marca"],
            descricao=it["descricao"],
            qtde=it["qtde"],
        ))
    db.commit()
    return RedirectResponse(url=f"/etiquetas/{reimp.id}/pdf", status_code=303)


# ---------------------------------------------------------------------------
# Geração individual (avulsa)
# ---------------------------------------------------------------------------

@router.get("/gerar")
def pagina_gerar(request: Request, db: Session = Depends(get_db)):
    total_cds = db.query(CD).filter(CD.ativo == True).count()  # noqa
    total_etiquetas = db.query(Etiqueta).count()
    return templates.TemplateResponse(
        request,
        "etiquetas/gerar.html",
        {
            "active_page": "gerar",
            "total_cds": total_cds,
            "total_etiquetas": total_etiquetas,
        },
    )


def _romaneio_query(db: Session, campanha_id: int | None, busca: str | None):
    """Monta a query do romaneio (uma linha por item de etiqueta)."""
    from sqlalchemy import or_
    q = (
        db.query(
            Etiqueta.id.label("etiqueta_id"),
            Etiqueta.num_caixa,
            Etiqueta.volume,
            Etiqueta.embalagem,
            Etiqueta.gerada_em,
            Etiqueta.pdf_path,
            Etiqueta.reimpressao,
            CD.id.label("cd_id"),
            CD.regional,
            CD.filial,
            CD.cidade,
            CD.uf,
            CD.zona_venda,
            CD.descricao_pacote.label("descricao_cd"),
            ItemEtiqueta.part_number,
            ItemEtiqueta.marca,
            ItemEtiqueta.descricao.label("descricao_item"),
            ItemEtiqueta.qtde,
        )
        .join(CD, CD.id == Etiqueta.cd_id)
        .outerjoin(ItemEtiqueta, ItemEtiqueta.etiqueta_id == Etiqueta.id)
        .filter(Etiqueta.reimpressao == False)  # noqa: E712 — romaneio mostra só originais
    )
    if campanha_id:
        q = q.filter(Etiqueta.campanha_id == campanha_id)
    if busca:
        termo = f"%{busca.strip()}%"
        q = q.filter(or_(
            CD.regional.ilike(termo),
            CD.filial.ilike(termo),
            CD.cidade.ilike(termo),
            CD.uf.ilike(termo),
            CD.zona_venda.ilike(termo),
            CD.descricao_pacote.ilike(termo),
            ItemEtiqueta.part_number.ilike(termo),
            ItemEtiqueta.marca.ilike(termo),
            ItemEtiqueta.descricao.ilike(termo),
        ))
    return q.order_by(Etiqueta.gerada_em.desc(), Etiqueta.num_caixa.desc(), ItemEtiqueta.id.asc())


@router.get("/historico")
def historico_redirect(campanha_id: int | None = Query(default=None)):
    suffix = f"?campanha_id={campanha_id}" if campanha_id else ""
    return RedirectResponse(url=f"/etiquetas/romaneio{suffix}", status_code=307)


@router.get("/romaneio")
def romaneio(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    campanha_id: int | None = Query(default=None),
    q: str | None = Query(default=None, alias="q"),
):
    per_page = 100
    base_q = _romaneio_query(db, campanha_id, q)
    total = base_q.count()
    linhas = base_q.offset((page - 1) * per_page).limit(per_page).all()
    campanhas = db.query(Campanha).order_by(Campanha.criada_em.desc()).all()
    return templates.TemplateResponse(
        request,
        "etiquetas/romaneio.html",
        {
            "linhas": linhas,
            "total": total,
            "page": page,
            "per_page": per_page,
            "active_page": "historico",
            "campanhas": campanhas,
            "campanha_id_filtro": campanha_id,
            "busca": q or "",
        },
    )


@router.get("/romaneio.csv")
def romaneio_csv(
    db: Session = Depends(get_db),
    campanha_id: int | None = Query(default=None),
    q: str | None = Query(default=None, alias="q"),
):
    import csv, io
    linhas = _romaneio_query(db, campanha_id, q).all()
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM para Excel
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "Nº CAIXA", "REGIONAL", "FILIAL (OPERAÇÃO)", "CIDADE", "UF",
        "CONTROLE MMBR", "DESCRIÇÃO", "PACOTE (ZONA VENDA)", "VOLUME",
        "EMBALAGEM", "DATA / HORA", "CODIGO", "MARCA", "DESCRIÇÃO", "QTDE",
    ])
    for r in linhas:
        writer.writerow([
            r.num_caixa,
            r.regional or "",
            r.filial or "",
            r.cidade or "",
            r.uf or "",
            r.cd_id,
            r.descricao_cd or "",
            r.zona_venda or "",
            r.volume or "",
            r.embalagem or "",
            r.gerada_em.strftime("%d/%m/%Y %H:%M") if r.gerada_em else "",
            r.part_number or "",
            r.marca or "",
            r.descricao_item or "",
            r.qtde if r.qtde is not None else "",
        ])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"romaneio_{stamp}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/")
def gerar_etiqueta(
    request: Request,
    cd_id: int = Form(...),
    volume: str = Form(default=""),
    num_caixas: int = Form(default=1),
    embalagem: str = Form(default=""),
    projeto: str = Form(default=""),
    transportador: str = Form(default=""),
    db: Session = Depends(get_db),
):
    cd = db.get(CD, cd_id)
    if not cd:
        return HTMLResponse('<p class="text-red-600">CD não encontrado.</p>')

    itens = db.query(ItemCD).filter(ItemCD.cd_id == cd_id).all()
    itens_dict = [
        {"part_number": it.part_number, "marca": it.marca, "descricao": it.descricao, "qtde": it.qtde}
        for it in itens
    ]

    transp = transportador.strip() or TRANSPORTADORA_PADRAO
    hoje = datetime.now().strftime("%d/%m/%Y")
    etiquetas_geradas = []

    for _ in range(max(1, num_caixas)):
        prox = proximo_num_caixa(db)
        dados_pdf = {
            "num_caixa": prox,
            "cd_id": cd_id,
            "cnpj": cd.cnpj or "",
            "regional": cd.regional or "",
            "filial": cd.filial or "",
            "cidade": cd.cidade or "",
            "uf": cd.uf or "",
            "zona_venda": cd.zona_venda or "",
            "volume": volume,
            "embalagem": embalagem,
            "projeto": projeto,
            "transportador": transp,
            "data": hoje,
        }
        pdf_path = pdf_svc.gerar_etiqueta(dados_pdf, itens_dict)
        etiqueta = Etiqueta(
            cd_id=cd_id,
            num_caixa=prox,
            volume=volume,
            embalagem=embalagem,
            projeto=projeto,
            transportador=transp,
            pdf_path=pdf_path,
        )
        db.add(etiqueta)
        db.flush()
        for it in itens:
            db.add(ItemEtiqueta(
                etiqueta_id=etiqueta.id,
                part_number=it.part_number,
                marca=it.marca,
                descricao=it.descricao,
                qtde=it.qtde,
            ))
        etiquetas_geradas.append({"id": etiqueta.id, "num_caixa": prox, "pdf_path": pdf_path})

    db.commit()
    return templates.TemplateResponse(
        request,
        "etiquetas/_sucesso.html",
        {"etiquetas": etiquetas_geradas},
    )


@router.get("/{etiqueta_id}/pdf")
def download_pdf(etiqueta_id: int, db: Session = Depends(get_db)):
    etiqueta = db.get(Etiqueta, etiqueta_id)
    if not etiqueta or not etiqueta.pdf_path:
        return HTMLResponse("PDF não encontrado", status_code=404)
    return FileResponse(
        etiqueta.pdf_path,
        media_type="application/pdf",
        filename=f"etiqueta_caixa_{etiqueta.num_caixa}.pdf",
    )
