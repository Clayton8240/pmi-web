"""Geração de etiquetas em PDF com ReportLab — portado do projeto desktop."""

import io
import math
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from typing import List, Dict

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, red
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.config import OUTPUT_FOLDER

# Caminhos das logos (relativos à raiz do projeto)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGO_MENTOR   = os.path.join(_BASE_DIR, "assets", "logo_mentor.png")
LOGO_HHGLOBAL = os.path.join(_BASE_DIR, "assets", "logo_hhglobal.png")
LOGO_PMI      = os.path.join(_BASE_DIR, "assets", "logo_pmi.png")


class PDFService:
    def __init__(self):
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    def gerar_lote(self, lote: List[Dict]) -> str:
        """Gera um único PDF multi-página com todas as etiquetas do lote.

        Cada item de `lote` é um dicionário com as chaves:
            'dados'       : dict passado a _desenhar (num_caixa, cd_id, ...)
            'itens'       : list de dict dos itens
            'reimpressao' : bool (opcional, default False)

        Retorna o caminho do arquivo PDF gerado.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(OUTPUT_FOLDER, f"LOTE_{timestamp}.pdf")

        label_size = (150 * mm, 100 * mm)
        c = canvas.Canvas(filepath, pagesize=label_size)
        width, height = label_size

        for i, item in enumerate(lote):
            if i > 0:
                c.showPage()
            self._desenhar(
                c,
                item["dados"],
                item["itens"],
                item.get("reimpressao", False),
                width,
                height,
            )

        c.save()
        return filepath

    def gerar_lote_paralelo(self, lote: List[Dict], workers: int = 4, threshold: int = 500) -> str:
        """Versão paralela de gerar_lote. Divide o lote em chunks, renderiza
        cada um em um worker separado e mescla os PDFs.
        Cai para a versão serial se o lote for pequeno ou workers<=1."""
        if not lote or workers <= 1 or len(lote) < threshold:
            return self.gerar_lote(lote)

        # importação tardia para não pagar custo quando não usado
        from pypdf import PdfReader, PdfWriter

        n = min(workers, len(lote))
        chunk_size = math.ceil(len(lote) / n)
        chunks = [lote[i:i + chunk_size] for i in range(0, len(lote), chunk_size)]

        with ProcessPoolExecutor(max_workers=n) as ex:
            blobs = list(ex.map(_render_chunk_to_bytes, chunks))

        writer = PdfWriter()
        for blob in blobs:
            reader = PdfReader(io.BytesIO(blob))
            for page in reader.pages:
                writer.add_page(page)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(OUTPUT_FOLDER, f"LOTE_{timestamp}.pdf")
        with open(filepath, "wb") as f:
            writer.write(f)
        return filepath

    def gerar_etiqueta(self, dados: Dict, itens: List[Dict], reimpressao: bool = False) -> str:
        """Gera uma etiqueta em PDF e retorna o caminho do arquivo."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        num_caixa = dados.get("num_caixa", 0)
        prefixo = "REIMP" if reimpressao else "ETIQ"
        filepath = os.path.join(OUTPUT_FOLDER, f"{prefixo}_Caixa{num_caixa}_{timestamp}.pdf")

        # Horizontal (landscape): 152 x 105 mm
        label_size = (150 * mm, 100 * mm)
        c = canvas.Canvas(filepath, pagesize=label_size)
        width, height = label_size

        self._desenhar(c, dados, itens, reimpressao, width, height)
        c.save()
        return filepath

    def gerar_etiqueta_bytes(self, dados: Dict, itens: List[Dict], reimpressao: bool = False) -> bytes:
        """Gera uma etiqueta em memória e retorna os bytes do PDF (sem salvar em disco)."""
        label_size = (150 * mm, 100 * mm)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=label_size)
        width, height = label_size
        self._desenhar(c, dados, itens, reimpressao, width, height)
        c.save()
        return buf.getvalue()

    def _desenhar(self, c: canvas.Canvas, dados: Dict, itens: List[Dict],
                  reimpressao: bool, width: float, height: float):
        ml = 5 * mm
        mr = 5 * mm
        mt = height - 5 * mm
        content_w = width - ml - mr
        y = mt

        def fit_size(text: str, font_name: str, base_size: float, max_w: float, min_size: float = 5.5) -> float:
            """Reduz o tamanho da fonte até o texto caber em max_w."""
            size = base_size
            while size >= min_size:
                if stringWidth(str(text), font_name, size) <= max_w:
                    return size
                size -= 0.5
            return min_size

        def box(x, y, w, h, text=None, align="L", bold=False, size=9, stroke=True):
            """Desenha célula com borda, fonte auto-reduzida e clipPath de segurança."""
            if stroke:
                c.rect(x, y, w, h)
            if text is not None:
                text = str(text)
                font_name = "Helvetica-Bold" if bold else "Helvetica"
                actual_size = fit_size(text, font_name, size, w - 6)
                c.saveState()
                # clipPath garante que nada vaze mesmo no pior caso
                p = c.beginPath()
                p.rect(x + 1, y + 0.5, w - 2, h - 1)
                c.clipPath(p, stroke=0, fill=0)
                c.setFont(font_name, actual_size)
                ty = y + h / 2 - actual_size * 0.35
                if align == "C":
                    c.drawCentredString(x + w / 2, ty, text)
                elif align == "R":
                    c.drawRightString(x + w - 3, ty, text)
                else:
                    c.drawString(x + 3, ty, text)
                c.restoreState()

        def wrap_text(text: str, font_name: str, size: float, max_w: float) -> list:
            """Quebra texto em palavras até caber em max_w por linha."""
            words = str(text).split()
            if not words:
                return [""]
            lines, current = [], words[0]
            for word in words[1:]:
                test = current + " " + word
                if stringWidth(test, font_name, size) <= max_w:
                    current = test
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
            return lines

        ITEM_FONT = "Helvetica"
        ITEM_SIZE_BASE = 6.0
        ITEM_SIZE_MIN = 4.0
        # ITEM_SIZE e ITEM_LINE_H são recalculados em _desenhar conforme o
        # nº de itens — declarados como variáveis locais (não constantes)
        ITEM_SIZE = ITEM_SIZE_BASE
        ITEM_LINE_H = 2.4 * mm
        ITEM_PAD    = 0.8 * mm

        def draw_cell_wrapped(x, y, w, h, lines, align="L", font_size=None, bold=False):
            """Desenha célula com borda e múltiplas linhas; alinha do topo se houver overflow."""
            c.rect(x, y, w, h)
            c.saveState()
            p = c.beginPath()
            p.rect(x + 1, y + 0.5, w - 2, h - 1)
            c.clipPath(p, stroke=0, fill=0)
            fs = font_size if font_size is not None else ITEM_SIZE
            line_h = fs * 0.4 * mm
            c.setFont("Helvetica-Bold" if bold else ITEM_FONT, fs)
            n = len(lines)
            block_h = n * line_h
            usable_h = h - ITEM_PAD
            if block_h <= usable_h:
                # cabe: centraliza verticalmente
                start_y = y + (h + block_h) / 2 - line_h * 0.75
            else:
                # não cabe: começa do topo; clipPath corta o excesso
                start_y = y + h - ITEM_PAD / 2 - line_h * 0.85
            for line in lines:
                if align == "C":
                    c.drawCentredString(x + w / 2, start_y, line)
                elif align == "R":
                    c.drawRightString(x + w - 3, start_y, line)
                else:
                    c.drawString(x + 3, start_y, line)
                start_y -= line_h
            c.restoreState()

        def box2line(x, y, w, h, label, value, lsize=7, vsize=9):
            """Célula com label em cima (menor) e valor embaixo."""
            c.rect(x, y, w, h)
            c.saveState()
            p = c.beginPath()
            p.rect(x + 1, y + 0.5, w - 2, h - 1)
            c.clipPath(p, stroke=0, fill=0)
            fn_l = "Helvetica-Bold"
            sz_l = fit_size(str(label), fn_l, lsize, w - 4)
            c.setFont(fn_l, sz_l)
            c.drawCentredString(x + w / 2, y + h * 0.62, str(label))
            fn_v = "Helvetica"
            sz_v = fit_size(str(value), fn_v, vsize, w - 4)
            c.setFont(fn_v, sz_v)
            c.drawCentredString(x + w / 2, y + h * 0.20, str(value))
            c.restoreState()
        # --- Topo ---
        top_h = 7 * mm            # compactado
        w_left  = content_w * 0.48
        w_right = content_w * 0.52
        # Mentor — esquerda (só logo, centrado)
        c.rect(ml, y - top_h, w_left, top_h)
        if os.path.exists(LOGO_MENTOR):
            c.drawImage(LOGO_MENTOR, ml + 2, y - top_h + 1,
                        width=w_left - 4, height=top_h - 2,
                        preserveAspectRatio=True, anchor='c', mask='auto')
        else:
            c.saveState()
            p = c.beginPath(); p.rect(ml + 1, y - top_h + 0.5, w_left - 2, top_h - 1)
            c.clipPath(p, stroke=0, fill=0)
            sz = fit_size("MENTOR BRASIL", "Helvetica-Bold", 13, w_left - 6)
            c.setFont("Helvetica-Bold", sz)
            c.drawCentredString(ml + w_left / 2, y - top_h + top_h / 2 - sz * 0.35, "MENTOR BRASIL")
            c.restoreState()

        # PMI — direita: texto "PHILIP MORRIS BRASIL" à esquerda + logo à direita
        x_pmi_cell = ml + w_left
        c.rect(x_pmi_cell, y - top_h, w_right, top_h)
        # Reserva ~40% da célula para o logo e os restantes 60% para o texto
        w_pmi_logo = w_right * 0.38
        w_pmi_txt  = w_right - w_pmi_logo - 2 * mm
        # Texto à esquerda
        c.saveState()
        p = c.beginPath(); p.rect(x_pmi_cell + 1, y - top_h + 0.5, w_pmi_txt, top_h - 1)
        c.clipPath(p, stroke=0, fill=0)
        sz_nome = fit_size("PHILIP MORRIS BRASIL", "Helvetica-Bold", 10, w_pmi_txt - 4)
        c.setFont("Helvetica-Bold", sz_nome)
        c.drawCentredString(x_pmi_cell + w_pmi_txt / 2,
                            y - top_h + top_h / 2 - sz_nome * 0.35,
                            "PHILIP MORRIS BRASIL")
        c.restoreState()
        # Logo à direita
        x_logo_pmi = x_pmi_cell + w_pmi_txt + 1 * mm
        if os.path.exists(LOGO_PMI):
            c.drawImage(LOGO_PMI, x_logo_pmi, y - top_h + 1,
                        width=w_pmi_logo - 2, height=top_h - 2,
                        preserveAspectRatio=True, anchor='e', mask='auto')
        else:
            c.saveState()
            p = c.beginPath(); p.rect(x_logo_pmi, y - top_h + 0.5, w_pmi_logo - 2, top_h - 1)
            c.clipPath(p, stroke=0, fill=0)
            sz = fit_size("PMI", "Helvetica-Bold", 12, w_pmi_logo - 4)
            c.setFont("Helvetica-Bold", sz)
            c.drawCentredString(x_logo_pmi + (w_pmi_logo - 2) / 2,
                                y - top_h + top_h / 2 - sz * 0.35, "PMI")
            c.restoreState()
        y -= top_h

        # --- Triagem (nº caixa / regional / transportador / ctrl mmbr) ---
        tri_h = 7 * mm
        w_num = 15 * mm
        w_reg = 38 * mm
        w_ctrl = 28 * mm
        w_transp = content_w - w_num - w_reg - w_ctrl
        box(ml, y - tri_h, w_num, tri_h, str(dados.get("num_caixa", "")), "C", True, 18)
        box(ml + w_num, y - tri_h, w_reg, tri_h,
            f"REGIONAL: {dados.get('regional', '')}", "C", True, 9)
        box2line(ml + w_num + w_reg, y - tri_h, w_transp, tri_h,
                 "TRANSPORTADO POR:", dados.get("transportador", ""), 7, 8)
        box2line(ml + w_num + w_reg + w_transp, y - tri_h, w_ctrl, tri_h,
                 "CTRL MMBR:", str(dados.get("cd_id", "")), 7, 8)
        y -= tri_h

        # --- Projeto / Volume / Embalagem / Data ---
        pv_h = 6.5 * mm
        w_proj = content_w * 0.35
        w_vol  = content_w * 0.18
        w_emb  = content_w * 0.22
        w_dat  = content_w - w_proj - w_vol - w_emb
        box2line(ml,                           y - pv_h, w_proj, pv_h, "PROJETO",   dados.get("projeto", ""))
        box2line(ml + w_proj,                  y - pv_h, w_vol,  pv_h, "VOLUME",    dados.get("volume", ""))
        box2line(ml + w_proj + w_vol,          y - pv_h, w_emb,  pv_h, "EMBALAGEM", dados.get("embalagem", ""))
        box2line(ml + w_proj + w_vol + w_emb,  y - pv_h, w_dat,  pv_h, "DATA",
                 dados.get("data", datetime.now().strftime("%d/%m/%Y")))
        y -= pv_h

        # --- Título ---
        title_h = 5 * mm
        box(ml, y - title_h, content_w, title_h, "ETIQUETA CDs PMI", "C", True, 10)
        y -= title_h

        # --- Filial + Cidade + UF (linha unificada, largura total) ---
        dest_h = 5.5 * mm
        filial_cidade_uf = (
            f"FILIAL: {dados.get('filial', '')}   "
            f"CIDADE: {dados.get('cidade', '')} / {dados.get('uf', '')}"
        )
        box(ml, y - dest_h, content_w, dest_h, filial_cidade_uf, "L", True, 9)
        y -= dest_h

        # --- Descrição do pacote ---
        zona_lbl_h = 3 * mm
        zona_val_h = 4.5 * mm
        box(ml, y - zona_lbl_h, content_w, zona_lbl_h,
            "DESCRIÇÃO DO PACOTE (ZONA DE VENDA)", "C", True, 7)
        y -= zona_lbl_h
        box(ml, y - zona_val_h, content_w, zona_val_h,
            str(dados.get("zona_venda", "")), "L", False, 9)
        y -= zona_val_h

        # --- Tabela de itens ---
        th = 3.5 * mm
        w_cod = 20 * mm
        w_mar = 44 * mm
        w_qtd = 14 * mm
        w_des = content_w - w_cod - w_mar - w_qtd
        cw = [w_cod, w_mar, w_des, w_qtd]
        headers = ["CÓDIGO", "MARCA", "DESCRIÇÃO", "QTDE"]
        hdr_aligns = ["L", "L", "L", "C"]
        x = ml
        for i, w in enumerate(cw):
            box(x, y - th, w, th, headers[i], hdr_aligns[i], True, 7)
            x += w
        y -= th

        foot_h = 0
        total_h = 4.0 * mm   # linha de total
        total_qtde = sum(int(it.get("qtde", 0) or 0) for it in itens)

        # Pad até 13 linhas para que todas as etiquetas tenham o mesmo tamanho.
        ROWS_FIXO = 13
        items_to_draw = list(itens)
        if len(items_to_draw) < ROWS_FIXO:
            items_to_draw = items_to_draw + [
                {"part_number": "", "marca": "", "descricao": "", "qtde": ""}
                for _ in range(ROWS_FIXO - len(items_to_draw))
            ]

        def _build_rows(font_size: float):
            line_h = font_size * 0.4 * mm          # 6pt -> 2.4mm (proporcional)
            min_row_h = max(3.5 * mm, line_h + ITEM_PAD)
            data = []
            for item in items_to_draw:
                vals_row = [
                    str(item.get("part_number", item.get("codigo", ""))),
                    str(item.get("marca", "")),
                    str(item.get("descricao", "")),
                    str(item.get("qtde", "")),
                ]
                all_lines = [wrap_text(vals_row[i], ITEM_FONT, font_size, cw[i] - 6) for i in range(len(cw))]
                max_lines = max(len(ls) for ls in all_lines)
                nat_h = max(min_row_h, max_lines * line_h + ITEM_PAD)
                data.append((all_lines, nat_h))
            return data, line_h, sum(d[1] for d in data)

        # Espaço disponível para itens + linha de total (3 mm de margem de segurança)
        items_area = y - foot_h - 3 * mm
        avail_rows = max(0.0, items_area - total_h)

        # Tenta reduzir a fonte até que toda a lista caiba sem comprimir
        chosen_size = ITEM_SIZE_BASE
        items_data, line_h, total_natural = _build_rows(chosen_size)
        while total_natural > avail_rows and chosen_size > ITEM_SIZE_MIN:
            chosen_size = max(ITEM_SIZE_MIN, chosen_size - 0.25)
            items_data, line_h, total_natural = _build_rows(chosen_size)

        ITEM_SIZE = chosen_size
        ITEM_LINE_H = line_h

        if total_natural <= avail_rows:
            row_heights = [d[1] for d in items_data]
        else:
            # Mesmo na fonte mínima ainda passa — comprime uniformemente
            n = len(items_data)
            uniform_h = max(line_h + ITEM_PAD, avail_rows / n) if n > 0 else line_h + ITEM_PAD
            row_heights = [min(d[1], uniform_h) for d in items_data]

        # QTDE em fonte maior e em negrito para legibilidade, mas limitada
        # à altura da linha (não pode ultrapassar) — máx 8pt.
        qtde_size = min(8.0, max(ITEM_SIZE + 1.5, ITEM_SIZE * 1.35))

        for (all_lines, _), row_h in zip(items_data, row_heights):
            x = ml
            for i, w in enumerate(cw):
                align = "C" if i == 3 else "L"
                if i == 3:
                    draw_cell_wrapped(x, y - row_h, w, row_h, all_lines[i], align,
                                      font_size=qtde_size, bold=True)
                else:
                    draw_cell_wrapped(x, y - row_h, w, row_h, all_lines[i], align)
                x += w
            y -= row_h

        # --- Linha de total (sempre desenhada) ---
        w_label = cw[0] + cw[1] + cw[2]
        box(ml,            y - total_h, w_label, total_h, "TOTAL GERAL", "R", True, 8)
        box(ml + w_label,  y - total_h, cw[3],   total_h, str(total_qtde), "C", True, 8)
        y -= total_h
        if reimpressao:
            c.setFillColor(red)
            c.setFont("Helvetica-Bold", 11)
            c.drawRightString(width - ml, height - 4 * mm, "*** REIMPRESSÃO ***")
            c.setFillColor(black)


def _render_chunk_to_bytes(chunk: List[Dict]) -> bytes:
    """Renderiza um chunk de etiquetas em um PDF em memória (usado por workers)."""
    svc = PDFService()
    label_size = (150 * mm, 100 * mm)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=label_size)
    width, height = label_size
    for i, item in enumerate(chunk):
        if i > 0:
            c.showPage()
        svc._desenhar(
            c,
            item["dados"],
            item["itens"],
            item.get("reimpressao", False),
            width,
            height,
        )
    c.save()
    return buf.getvalue()
