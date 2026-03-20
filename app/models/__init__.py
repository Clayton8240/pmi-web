"""
Modelos SQLAlchemy — todos definidos aqui para evitar imports circulares.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


# ---------------------------------------------------------------------------
# Campanhas
# ---------------------------------------------------------------------------

class Campanha(Base):
    """Representa uma rodada/ciclo de distribuição (ex.: PMI Q1 2026)."""
    __tablename__ = "campanhas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    criada_em = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="ativa")   # ativa | encerrada

    itens_cd = relationship("ItemCD", back_populates="campanha")
    etiquetas = relationship("Etiqueta", back_populates="campanha")


# ---------------------------------------------------------------------------
# Catálogo de materiais
# ---------------------------------------------------------------------------

class Material(Base):
    __tablename__ = "materiais"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_number = Column(String(50), unique=True, nullable=False, index=True)
    descricao = Column(String(255), nullable=False)
    marca = Column(String(100))
    unidade = Column(String(20), default="UN")
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    volumes = relationship("VolumePorCaixa", back_populates="material", cascade="all, delete-orphan")
    itens_cd = relationship("ItemCD", back_populates="material")


class VolumePorCaixa(Base):
    """Configuração de embalagem por caixa para um material.
    Ex.: HH-0059 → 10 unidades/cx, descrição '10UN/CX'
    """
    __tablename__ = "volumes_caixa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("materiais.id", ondelete="CASCADE"), nullable=False)
    descricao = Column(String(100), nullable=False)   # texto na etiqueta: "10UN/CX", "1CX/KIT"
    qtde_por_cx = Column(Integer, nullable=False)     # quantas unidades cabem em 1 caixa
    ativo = Column(Boolean, default=True)

    material = relationship("Material", back_populates="volumes")


# ---------------------------------------------------------------------------
# CDs (Centros de Distribuição / Regiões)
# ---------------------------------------------------------------------------

class CD(Base):
    __tablename__ = "cds"

    id = Column(Integer, primary_key=True)            # Controle MMBR (vem da planilha)
    cnpj = Column(String(20))
    cidade = Column(String(100))
    uf = Column(String(2))
    regional = Column(String(100))
    filial = Column(String(150))
    zona_venda = Column(String(150))
    descricao_pacote = Column(Text)
    ativo = Column(Boolean, default=True)
    importado_em = Column(DateTime, default=datetime.utcnow)

    itens = relationship("ItemCD", back_populates="cd", cascade="all, delete-orphan")
    etiquetas = relationship("Etiqueta", back_populates="cd")


class ItemCD(Base):
    """Itens do pedido de cada CD (importados da planilha de campanha)."""
    __tablename__ = "itens_cd"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cd_id = Column(Integer, ForeignKey("cds.id", ondelete="CASCADE"), nullable=False)
    campanha_id = Column(Integer, ForeignKey("campanhas.id", ondelete="CASCADE"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materiais.id"), nullable=True)
    part_number = Column(String(50), nullable=False)
    marca = Column(String(100))
    descricao = Column(String(255))
    qtde = Column(Integer)

    cd = relationship("CD", back_populates="itens")
    campanha = relationship("Campanha", back_populates="itens_cd")
    material = relationship("Material", back_populates="itens_cd")


# ---------------------------------------------------------------------------
# Etiquetas geradas
# ---------------------------------------------------------------------------

class Etiqueta(Base):
    __tablename__ = "etiquetas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cd_id = Column(Integer, ForeignKey("cds.id"), nullable=False)
    campanha_id = Column(Integer, ForeignKey("campanhas.id"), nullable=True, index=True)
    num_caixa = Column(Integer, nullable=False, index=True)
    volume = Column(String(255))
    embalagem = Column(String(100))
    projeto = Column(String(100))
    transportador = Column(String(200))
    pdf_path = Column(String(500))
    gerada_em = Column(DateTime, default=datetime.utcnow)
    reimpressao = Column(Boolean, default=False)

    cd = relationship("CD", back_populates="etiquetas")
    campanha = relationship("Campanha", back_populates="etiquetas")
    itens = relationship("ItemEtiqueta", back_populates="etiqueta", cascade="all, delete-orphan")


class ItemEtiqueta(Base):
    """Snapshot dos itens no momento em que a etiqueta foi gerada."""
    __tablename__ = "itens_etiqueta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    etiqueta_id = Column(Integer, ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=False)
    part_number = Column(String(50))
    marca = Column(String(100))
    descricao = Column(String(255))
    qtde = Column(Integer)

    etiqueta = relationship("Etiqueta", back_populates="itens")
