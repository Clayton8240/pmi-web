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
