"""Serviço de cálculo automático de volumes por CD."""

import math
from sqlalchemy.orm import Session
from app.models import ItemCD, VolumePorCaixa


def calcular_volume_cd(cd_id: int, db: Session, campanha_id: int | None = None) -> dict:
    """
    Para cada item do CD (filtrando pela campanha se informada), busca a
    configuração de volume no catálogo, calcula caixas necessárias e monta
    o texto de volume para a etiqueta.

    Retorna:
        {
            "volume_texto": "10UN/CX | 1CX/KIT",
            "num_caixas": 3,
            "detalhes": [...],
            "itens_sem_catalogo": ["PMI-XXXX", ...]
        }
    """
    q = db.query(ItemCD).filter(ItemCD.cd_id == cd_id)
    if campanha_id is not None:
        q = q.filter(ItemCD.campanha_id == campanha_id)
    itens = q.all()

    volume_descs: list[str] = []   # descrições únicas (ordem inserção)
    num_caixas_total = 0
    detalhes = []
    sem_catalogo = []

    for item in itens:
        if not item.material_id:
            sem_catalogo.append(item.part_number)
            detalhes.append({
                "part_number": item.part_number,
                "descricao": item.descricao,
                "qtde": item.qtde,
                "volume_desc": None,
                "qtde_por_cx": None,
                "num_caixas": None,
            })
            continue

        vol_cfg: VolumePorCaixa | None = (
            db.query(VolumePorCaixa)
            .filter(
                VolumePorCaixa.material_id == item.material_id,
                VolumePorCaixa.ativo == True,  # noqa: E712
            )
            .first()
        )

        if not vol_cfg:
            sem_catalogo.append(item.part_number)
            detalhes.append({
                "part_number": item.part_number,
                "descricao": item.descricao,
                "qtde": item.qtde,
                "volume_desc": None,
                "qtde_por_cx": None,
                "num_caixas": None,
            })
            continue

        qtde = item.qtde or 0
        num_caixas_item = math.ceil(qtde / vol_cfg.qtde_por_cx) if vol_cfg.qtde_por_cx > 0 else 1
        num_caixas_total += num_caixas_item

        if vol_cfg.descricao not in volume_descs:
            volume_descs.append(vol_cfg.descricao)

        detalhes.append({
            "part_number": item.part_number,
            "descricao": item.descricao,
            "qtde": qtde,
            "volume_desc": vol_cfg.descricao,
            "qtde_por_cx": vol_cfg.qtde_por_cx,
            "num_caixas": num_caixas_item,
        })

    return {
        "volume_texto": " | ".join(volume_descs) if volume_descs else "",
        "num_caixas": max(1, num_caixas_total),
        "detalhes": detalhes,
        "itens_sem_catalogo": sem_catalogo,
    }


def proximo_num_caixa(db: Session, campanha_id: int | None = None) -> int:
    """Retorna o próximo número de caixa.
    Se campanha_id for fornecido, a numeração é isolada dentro da campanha.
    Caso contrário, é global (legado).
    """
    from sqlalchemy import func
    from app.models import Etiqueta
    q = db.query(func.max(Etiqueta.num_caixa))
    if campanha_id is not None:
        q = q.filter(Etiqueta.campanha_id == campanha_id)
    resultado = q.scalar()
    return (resultado or 0) + 1


# ---------------------------------------------------------------------------
# Empacotamento por capacidade
# ---------------------------------------------------------------------------

def _capacidade_material(db: Session, material_id: int) -> int | None:
    cfg = (
        db.query(VolumePorCaixa)
        .filter(
            VolumePorCaixa.material_id == material_id,
            VolumePorCaixa.ativo == True,  # noqa: E712
        )
        .order_by(VolumePorCaixa.id.desc())
        .first()
    )
    if not cfg or cfg.qtde_por_cx <= 0:
        return None
    return cfg.qtde_por_cx


def materiais_pendentes_capacidade(db: Session, campanha_id: int) -> list[dict]:
    """Retorna lista de materiais únicos da campanha que ainda não têm
    `VolumePorCaixa` configurado (ou que têm capacidade <= 0)."""
    from app.models import Material
    rows = (
        db.query(ItemCD.material_id, ItemCD.part_number, ItemCD.descricao, ItemCD.marca)
        .filter(ItemCD.campanha_id == campanha_id)
        .filter(ItemCD.material_id.isnot(None))
        .distinct()
        .all()
    )
    cap_cache = _bulk_capacidades(db)
    mat_ids_pendentes = [r[0] for r in rows if cap_cache.get(r[0]) is None]
    materiais = {
        m.id: m
        for m in db.query(Material).filter(Material.id.in_(mat_ids_pendentes)).all()
    } if mat_ids_pendentes else {}
    pendentes = []
    vistos: set[int] = set()
    for mat_id, pn, desc, marca in rows:
        if mat_id in vistos or cap_cache.get(mat_id) is not None:
            continue
        vistos.add(mat_id)
        mat = materiais.get(mat_id)
        pendentes.append({
            "material_id": mat_id,
            "part_number": (mat.part_number if mat else pn),
            "descricao": (mat.descricao if mat else desc) or "",
            "marca": (mat.marca if mat else marca) or "",
        })
    pendentes.sort(key=lambda x: x["part_number"])
    return pendentes


def montar_pacotes_cd(
    cd_id: int,
    db: Session,
    campanha_id: int,
    cap_cache: dict[int, int | None] | None = None,
    itens: list | None = None,
) -> list[list[dict]]:
    """Aplica a regra de empacotamento por capacidade.

    Cada material tem uma capacidade máxima por pacote (`qtde_por_cx`).
    Quando vários materiais convivem no mesmo pacote, a capacidade do
    pacote é o MENOR dentre os materiais ainda pendentes — assim o item
    de menor capacidade é o gargalo. Quando um material se esgota, o
    cálculo passa a usar a capacidade dos remanescentes.

    Aceita opcionalmente:
        cap_cache: dict {material_id: capacidade} pré-carregado em bulk.
        itens:     lista de ItemCD já consultada (evita query individual).

    Retorna lista de pacotes; cada pacote é uma lista de dicts:
        {"part_number", "marca", "descricao", "qtde"}
    """
    if itens is None:
        itens = (
            db.query(ItemCD)
            .filter(ItemCD.cd_id == cd_id, ItemCD.campanha_id == campanha_id)
            .order_by(ItemCD.id)
            .all()
        )

    # pendentes: (part_number, marca, descricao, qtde_restante, capacidade)
    pendentes: list[list] = []
    for it in itens:
        qtde = int(it.qtde or 0)
        if qtde <= 0:
            continue
        if cap_cache is not None:
            cap = cap_cache.get(it.material_id) if it.material_id else None
        else:
            cap = _capacidade_material(db, it.material_id) if it.material_id else None
        if cap is None:
            # Sem capacidade definida: trata como pacote individual ilimitado para
            # não silenciar o item; o controlador deve impedir esse cenário.
            cap = qtde
        pendentes.append([
            it.part_number or "",
            it.marca or "",
            it.descricao or "",
            qtde,
            cap,
        ])

    # Ordena por menor capacidade primeiro — assim os itens mais restritivos
    # são consumidos antes e o último pacote pode usar a capacidade maior.
    pendentes.sort(key=lambda r: r[4])

    # Limite físico de linhas que cabem na etiqueta impressa.
    MAX_LINHAS_PACOTE = 13

    pacotes: list[list[dict]] = []
    while pendentes:
        cap_pkg = min(r[4] for r in pendentes)
        restante = cap_pkg
        pkg: list[dict] = []
        i = 0
        while restante > 0 and i < len(pendentes) and len(pkg) < MAX_LINHAS_PACOTE:
            pn, mc, ds, q, c = pendentes[i]
            take = min(q, restante)
            if take > 0:
                pkg.append({
                    "part_number": pn,
                    "marca": mc,
                    "descricao": ds,
                    "qtde": take,
                })
                q -= take
                restante -= take
                if q == 0:
                    pendentes.pop(i)
                    continue
                else:
                    pendentes[i][3] = q
            i += 1
        if not pkg:
            # Salvaguarda: evita loop infinito
            break
        pacotes.append(pkg)

    return pacotes


def _bulk_capacidades(db: Session) -> dict[int, int | None]:
    """Carrega todas as capacidades ativas em uma única query.
    Retorna {material_id: qtde_por_cx} (None se inválida)."""
    rows = (
        db.query(VolumePorCaixa.material_id, VolumePorCaixa.qtde_por_cx)
        .filter(VolumePorCaixa.ativo == True)  # noqa: E712
        .order_by(VolumePorCaixa.id.desc())
        .all()
    )
    cache: dict[int, int | None] = {}
    for mat_id, qtde in rows:
        if mat_id in cache:
            continue  # já temos a mais recente (id desc)
        cache[mat_id] = qtde if qtde and qtde > 0 else None
    return cache


def contar_pacotes_campanha(db: Session, campanha_id: int) -> dict[int, int]:
    """Conta quantos pacotes (etiquetas) cada CD da campanha vai gerar.

    Otimizado: 2 queries totais (capacidades + itens), sem N+1.
    """
    cap_cache = _bulk_capacidades(db)
    itens_all = (
        db.query(ItemCD)
        .filter(ItemCD.campanha_id == campanha_id)
        .order_by(ItemCD.cd_id, ItemCD.id)
        .all()
    )
    por_cd: dict[int, list] = {}
    for it in itens_all:
        por_cd.setdefault(it.cd_id, []).append(it)
    resultado: dict[int, int] = {}
    for cd_id, itens in por_cd.items():
        resultado[cd_id] = len(
            montar_pacotes_cd(cd_id, db, campanha_id, cap_cache=cap_cache, itens=itens)
        )
    return resultado
