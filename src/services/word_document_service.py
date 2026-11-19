"""Read DOCX content and build a preview-only HTML representation."""

from html import escape
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import quoteattr
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


class WordDocumentService:
    """Extract paragraphs, tables, and preview placeholders from a DOCX."""

    _WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    _TWIPS_PER_PIXEL = 15
    _DEFAULT_PAGE_CONTENT_TWIPS = 9360
    _WORD_NS_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _LATEX_PATTERN = re.compile(
        r"\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|"
        r"\\begin\{(?:equation|align|gather)\*?\}.*?\\end\{(?:equation|align|gather)\*?\}|"
        r"(?<!\\)\$(?!\s)(?:\\.|[^$\n])+\$",
        re.DOTALL,
    )

    def read(self, file_path: str) -> tuple[bytes, list[str]]:
        """Return original file bytes and preview blocks without changing the source."""
        path = Path(file_path)
        data = path.read_bytes()
        if path.suffix.lower() != ".docx":
            raise ValueError("Поддерживается только формат Word .docx.")

        try:
            with ZipFile(path) as archive:
                document_xml = archive.read("word/document.xml")
        except (BadZipFile, KeyError) as error:
            raise ValueError("Файл не является корректным документом DOCX.") from error

        try:
            root = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as error:
            raise ValueError("Не удалось прочитать структуру документа DOCX.") from error

        body = root.find(f"{self._WORD_NS}body")
        if body is None:
            return data, ["<p></p>"]
        self._page_content_width_twips = self._page_content_width(body)
        blocks = self._render_blocks(body)
        return data, blocks or ["<p></p>"]

    def apply_appearance(self, document_data: bytes, text_color: str, background_color: str) -> bytes:
        """Return a DOCX copy with text and whole-page background colors applied."""
        for color in (text_color, background_color):
            if len(color) != 7 or color[0] != "#" or any(
                character not in "0123456789abcdefABCDEF" for character in color[1:]
            ):
                raise ValueError("colors must use the #RRGGBB format")

        namespace = f"{{{self._WORD_NS_URI}}}"
        with ZipFile(BytesIO(document_data)) as source_archive:
            try:
                document_xml = source_archive.read("word/document.xml")
            except KeyError as error:
                raise ValueError("DOCX document.xml is missing") from error
            try:
                root = ElementTree.fromstring(document_xml)
            except ElementTree.ParseError as error:
                raise ValueError("DOCX document.xml is not valid XML") from error
            namespace_declarations = {
                prefix: uri
                for _, (prefix, uri) in ElementTree.iterparse(
                    BytesIO(document_xml), events=("start-ns",)
                )
            }
            run_count = 0
            for run in root.iter(f"{namespace}r"):
                properties = run.find(f"{namespace}rPr")
                if properties is None:
                    properties = ElementTree.Element(f"{namespace}rPr")
                    run.insert(0, properties)
                color_element = properties.find(f"{namespace}color")
                if color_element is None:
                    color_element = ElementTree.SubElement(properties, f"{namespace}color")
                color_element.set(f"{namespace}val", color[1:].upper())
                for attribute in ("themeColor", "themeTint", "themeShade"):
                    color_element.attrib.pop(f"{namespace}{attribute}", None)
                run_count += 1
            if run_count == 0:
                raise ValueError("DOCX contains no text runs to color")

            background = root.find(f"{namespace}background")
            if background is None:
                background = ElementTree.Element(f"{namespace}background")
            for existing in root.findall(f"{namespace}background"):
                root.remove(existing)
            background.set(f"{namespace}color", background_color[1:].upper())
            for attribute in ("themeColor", "themeTint", "themeShade"):
                background.attrib.pop(f"{namespace}{attribute}", None)
            root.insert(0, background)

            updated_xml = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            updated_xml = self._preserve_namespace_declarations(updated_xml, namespace_declarations)
            output = BytesIO()
            with ZipFile(output, "w") as result_archive:
                for item in source_archive.infolist():
                    contents = updated_xml if item.filename == "word/document.xml" else source_archive.read(item.filename)
                    result_archive.writestr(item, contents)
        return output.getvalue()

    @staticmethod
    def _preserve_namespace_declarations(xml_data: bytes, declarations: dict[str, str]) -> bytes:
        """Restore namespace aliases that ElementTree omits when they appear only in attribute values.

        OOXML uses values such as ``mc:Ignorable="w14 wp14"`` where the listed
        prefixes must remain declared even when no element uses those namespaces.
        ElementTree drops such unused declarations during serialization.
        """
        root_tag = re.search(rb"<(?![?!])[^>]+>", xml_data)
        if root_tag is None:
            raise ValueError("Serialized DOCX document has no root element")

        opening_tag = root_tag.group(0)
        missing: list[str] = []
        for prefix, uri in declarations.items():
            attribute = b"xmlns" if not prefix else b"xmlns:" + prefix.encode("utf-8")
            if re.search(rb"(?:^|\s)" + re.escape(attribute) + rb"\s*=", opening_tag):
                continue
            missing.append(f" {attribute.decode('utf-8')}={quoteattr(uri)}")

        if not missing:
            return xml_data
        insertion = "".join(missing).encode("utf-8")
        updated_tag = opening_tag[:-1] + insertion + b">"
        return xml_data[:root_tag.start()] + updated_tag + xml_data[root_tag.end():]

    def _page_content_width(self, body: ElementTree.Element) -> int:
        """Get the page's printable width from its section properties."""
        sections = list(body.iter(f"{self._WORD_NS}sectPr"))
        if not sections:
            return self._DEFAULT_PAGE_CONTENT_TWIPS
        section = sections[-1]
        page_size = section.find(f"{self._WORD_NS}pgSz")
        page_margins = section.find(f"{self._WORD_NS}pgMar")
        page_width = page_size.get(f"{self._WORD_NS}w", "12240") if page_size is not None else "12240"
        margin_left = page_margins.get(f"{self._WORD_NS}left", "1440") if page_margins is not None else "1440"
        margin_right = page_margins.get(f"{self._WORD_NS}right", "1440") if page_margins is not None else "1440"
        if not all(value.isdigit() for value in (page_width, margin_left, margin_right)):
            return self._DEFAULT_PAGE_CONTENT_TWIPS
        return max(1, int(page_width) - int(margin_left) - int(margin_right))

    def _render_blocks(self, parent: ElementTree.Element) -> list[str]:
        """Render document paragraphs and table rows in their original order."""
        blocks: list[str] = []
        for element in parent:
            kind = self._local_name(element.tag)
            if kind == "p":
                blocks.append(self._render_paragraph(element))
            elif kind == "tbl":
                blocks.extend(self._render_table(element))
            elif kind in {"oMath", "oMathPara"}:
                blocks.append(self._formula_placeholder("".join(element.itertext())))
            elif kind not in {"sectPr", "pPr", "tblPr", "trPr", "tcPr"}:
                blocks.extend(self._render_blocks(element))
        return blocks

    def _render_paragraph(self, paragraph: ElementTree.Element) -> str:
        properties = paragraph.find(f"{self._WORD_NS}pPr")
        styles: list[str] = []
        if properties is not None:
            alignment = properties.find(f"{self._WORD_NS}jc")
            if alignment is not None:
                value = self._value(alignment, "val", "left")
                styles.append(f"text-align: {'justify' if value == 'both' else value}")
            indent = properties.find(f"{self._WORD_NS}ind")
            if indent is not None:
                for attribute, css_property in (
                    ("left", "margin-left"),
                    ("right", "margin-right"),
                    ("firstLine", "text-indent"),
                ):
                    value = indent.get(f"{self._WORD_NS}{attribute}")
                    if value and value.isdigit():
                        styles.append(f"{css_property}: {int(value) / 20:g}pt")
                hanging = indent.get(f"{self._WORD_NS}hanging")
                if hanging and hanging.isdigit():
                    styles.append(f"text-indent: -{int(hanging) / 20:g}pt")
            spacing = properties.find(f"{self._WORD_NS}spacing")
            if spacing is not None:
                for attribute, css_property in (("before", "margin-top"), ("after", "margin-bottom")):
                    value = spacing.get(f"{self._WORD_NS}{attribute}")
                    if value and value.isdigit():
                        styles.append(f"{css_property}: {int(value) / 20:g}pt")
                line = spacing.get(f"{self._WORD_NS}line", "")
                if line.isdigit():
                    if spacing.get(f"{self._WORD_NS}lineRule", "auto") == "auto":
                        styles.append(f"line-height: {int(line) / 240 * 100:g}%")
                    else:
                        styles.append(f"line-height: {int(line) / 20:g}pt")

        content = "".join(self._render_inline(child) for child in paragraph if self._local_name(child.tag) != "pPr")
        style_attribute = f" style=\"{'; '.join(styles)}\"" if styles else ""
        return f"<p{style_attribute}>{content or '&nbsp;'}</p>"

    def _render_inline(self, element: ElementTree.Element) -> str:
        kind = self._local_name(element.tag)
        if kind == "r":
            run_properties = element.find(f"{self._WORD_NS}rPr")
            styles: list[str] = []
            if run_properties is not None:
                if run_properties.find(f"{self._WORD_NS}b") is not None:
                    styles.append("font-weight: bold")
                if run_properties.find(f"{self._WORD_NS}i") is not None:
                    styles.append("font-style: italic")
                if run_properties.find(f"{self._WORD_NS}u") is not None:
                    styles.append("text-decoration: underline")
                size = run_properties.find(f"{self._WORD_NS}sz")
                if size is not None and (value := size.get(f"{self._WORD_NS}val", "")).isdigit():
                    styles.append(f"font-size: {int(value) / 2:g}pt")
                fonts = run_properties.find(f"{self._WORD_NS}rFonts")
                if fonts is not None and (font := fonts.get(f"{self._WORD_NS}ascii")):
                    styles.append(f"font-family: '{escape(font)}'")
                color = run_properties.find(f"{self._WORD_NS}color")
                if color is not None and (value := color.get(f"{self._WORD_NS}val", "")):
                    if len(value) == 6 and all(char in "0123456789abcdefABCDEF" for char in value):
                        styles.append(f"color: #{value}")
            content = "".join(self._render_inline(child) for child in element if self._local_name(child.tag) != "rPr")
            if styles and "<table" not in content:
                return f"<span style=\"{'; '.join(styles)}\">{content}</span>"
            return content

        if kind == "t":
            return self._render_text(element.text or "")
        if kind == "tab":
            return "&#9;"
        if kind in {"br", "cr"}:
            return "<br>"
        if kind in {"drawing", "pict", "object"}:
            return self._image_placeholder(element)
        if kind in {"oMath", "oMathPara"}:
            return self._formula_placeholder("".join(element.itertext()))
        if kind in {"instrText", "delText", "rPr", "pPr"}:
            return ""
        return "".join(self._render_inline(child) for child in element)

    def _render_text(self, text: str) -> str:
        """Escape ordinary text and replace delimited LaTeX only in the preview."""
        parts: list[str] = []
        position = 0
        for match in self._LATEX_PATTERN.finditer(text):
            parts.append(escape(text[position:match.start()]))
            parts.append(self._formula_placeholder(match.group()))
            position = match.end()
        parts.append(escape(text[position:]))
        return "".join(parts)

    def _render_table(self, table: ElementTree.Element) -> list[str]:
        """Render table rows as bordered HTML tables so pagination can split rows."""
        table_properties = table.find(f"{self._WORD_NS}tblPr")
        table_styles: list[str] = ["border-collapse: collapse", "margin: 0"]
        table_width_twips = self._page_content_width_twips
        if table_properties is not None:
            alignment = table_properties.find(f"{self._WORD_NS}jc")
            if alignment is not None and self._value(alignment, "val", "left") == "center":
                table_styles.append("margin-left: auto; margin-right: auto")
            borders = table_properties.find(f"{self._WORD_NS}tblBorders")
            if borders is not None:
                for side in ("top", "right", "bottom", "left"):
                    border = borders.find(f"{self._WORD_NS}{side}")
                    if border is not None:
                        table_styles.append(self._border_style(side, border))
            width = table_properties.find(f"{self._WORD_NS}tblW")
            if width is not None:
                width_value = width.get(f"{self._WORD_NS}w", "")
                if width_value.isdigit() and width.get(f"{self._WORD_NS}type") == "dxa":
                    table_width_twips = max(1, int(width_value))
                    width_percent = int(width_value) / self._page_content_width_twips * 100
                    table_styles.append(f"width: {min(100, width_percent):g}%")
                elif width_value.isdigit() and width.get(f"{self._WORD_NS}type") == "pct":
                    width_percent = min(100, int(width_value) / 50)
                    table_width_twips = max(1, int(self._page_content_width_twips * width_percent / 100))
                    table_styles.append(f"width: {width_percent:g}%")

        grid = table.find(f"{self._WORD_NS}tblGrid")
        grid_widths = []
        if grid is not None:
            for column in grid.findall(f"{self._WORD_NS}gridCol"):
                value = column.get(f"{self._WORD_NS}w", "")
                grid_widths.append(int(value) / self._TWIPS_PER_PIXEL if value.isdigit() else 0)
        if table_width_twips == self._page_content_width_twips and grid_widths and not (table_properties is not None and table_properties.find(f"{self._WORD_NS}tblW") is not None):
            table_width_twips = max(1, round(sum(grid_widths) * self._TWIPS_PER_PIXEL))

        rows = table.findall(f"{self._WORD_NS}tr")
        row_columns: list[list[tuple[int, int]]] = []
        for row in rows:
            columns: list[tuple[int, int]] = []
            column_index = 0
            for cell in row.findall(f"{self._WORD_NS}tc"):
                properties = cell.find(f"{self._WORD_NS}tcPr")
                grid_span = properties.find(f"{self._WORD_NS}gridSpan") if properties is not None else None
                value = grid_span.get(f"{self._WORD_NS}val", "1") if grid_span is not None else "1"
                span = max(1, int(value)) if value.isdigit() else 1
                columns.append((column_index, span))
                column_index += span
            row_columns.append(columns)

        row_spans: dict[tuple[int, int], int] = {}
        continuation_cells: set[tuple[int, int]] = set()
        merged_rows: set[int] = set()
        for row_index, row in enumerate(rows):
            cells = row.findall(f"{self._WORD_NS}tc")
            for cell_index, cell in enumerate(cells):
                properties = cell.find(f"{self._WORD_NS}tcPr")
                merge = properties.find(f"{self._WORD_NS}vMerge") if properties is not None else None
                if merge is None or self._value(merge, "val", "continue") != "restart":
                    continue
                column_index = row_columns[row_index][cell_index][0]
                span = 1
                for following_row in range(row_index + 1, len(rows)):
                    target_index = next(
                        (index for index, (column, _) in enumerate(row_columns[following_row]) if column == column_index),
                        None,
                    )
                    if target_index is None:
                        break
                    target = rows[following_row].findall(f"{self._WORD_NS}tc")[target_index]
                    target_properties = target.find(f"{self._WORD_NS}tcPr")
                    target_merge = target_properties.find(f"{self._WORD_NS}vMerge") if target_properties is not None else None
                    if target_merge is None or self._value(target_merge, "val", "continue") == "restart":
                        break
                    span += 1
                    continuation_cells.add((following_row, target_index))
                    merged_rows.add(following_row)
                if span > 1:
                    row_spans[(row_index, cell_index)] = span
                    merged_rows.add(row_index)

        rendered_rows: list[str] = []
        for row_index, row in enumerate(rows):
            cells: list[str] = []
            column_index = 0
            row_styles: list[str] = []
            row_properties = row.find(f"{self._WORD_NS}trPr")
            row_height = row_properties.find(f"{self._WORD_NS}trHeight") if row_properties is not None else None
            if row_height is not None:
                value = row_height.get(f"{self._WORD_NS}val", "")
                if value.isdigit():
                    row_styles.append(f"height: {int(value) / self._TWIPS_PER_PIXEL:g}px")
            for cell_index, cell in enumerate(row.findall(f"{self._WORD_NS}tc")):
                cell_properties = cell.find(f"{self._WORD_NS}tcPr")
                cell_styles = ["border: 1px solid #8c929b", "padding: 3px", "vertical-align: top"]
                attributes: list[str] = []
                span = 1
                if cell_properties is not None:
                    grid_span = cell_properties.find(f"{self._WORD_NS}gridSpan")
                    if grid_span is not None:
                        value = grid_span.get(f"{self._WORD_NS}val", "1")
                        if value.isdigit():
                            span = max(1, int(value))
                            if span > 1:
                                attributes.append(f'colspan="{span}"')
                    cell_width = cell_properties.find(f"{self._WORD_NS}tcW")
                    width_value = cell_width.get(f"{self._WORD_NS}w", "") if cell_width is not None else ""
                    if width_value.isdigit() and cell_width.get(f"{self._WORD_NS}type") == "dxa":
                        cell_styles.append(f"width: {int(width_value) / table_width_twips * 100:g}%")
                    elif grid_widths and column_index < len(grid_widths) and grid_widths[column_index]:
                        span_width = sum(grid_widths[column_index:column_index + span])
                        cell_styles.append(f"width: {span_width / (table_width_twips / self._TWIPS_PER_PIXEL) * 100:g}%")
                    shading = cell_properties.find(f"{self._WORD_NS}shd")
                    fill = shading.get(f"{self._WORD_NS}fill", "") if shading is not None else ""
                    if len(fill) == 6 and all(char in "0123456789abcdefABCDEF" for char in fill):
                        cell_styles.append(f"background-color: #{fill}")
                    vertical_alignment = cell_properties.find(f"{self._WORD_NS}vAlign")
                    if vertical_alignment is not None:
                        value = self._value(vertical_alignment, "val", "top")
                        cell_styles.append(f"vertical-align: {'middle' if value == 'center' else value}")
                    margins = cell_properties.find(f"{self._WORD_NS}tcMar")
                    if margins is not None:
                        for side in ("top", "right", "bottom", "left"):
                            margin = margins.find(f"{self._WORD_NS}{side}")
                            value = margin.get(f"{self._WORD_NS}w", "") if margin is not None else ""
                            if value.isdigit():
                                cell_styles.append(f"padding-{side}: {int(value) / self._TWIPS_PER_PIXEL:g}px")
                    borders = cell_properties.find(f"{self._WORD_NS}tcBorders")
                    if borders is not None:
                        for side in ("top", "right", "bottom", "left"):
                            border = borders.find(f"{self._WORD_NS}{side}")
                            if border is not None:
                                cell_styles.append(self._border_style(side, border))

                if (row_index, cell_index) in continuation_cells:
                    column_index += span
                    continue
                row_span = row_spans.get((row_index, cell_index), 1)
                if row_span > 1:
                    attributes.append(f'rowspan="{row_span}"')

                cell_content = "".join(self._render_blocks(cell)) or "<p>&nbsp;</p>"
                style = "; ".join(cell_styles)
                attrs = " " + " ".join(attributes) if attributes else ""
                cells.append(f"<td{attrs} style=\"{style}\">{cell_content}</td>")
                column_index += span
            row_style = f" style=\"{'; '.join(row_styles)}\"" if row_styles else ""
            rendered_rows.append(f"<tr{row_style}>{''.join(cells)}</tr>")

        rendered_blocks: list[str] = []
        row_index = 0
        while row_index < len(rendered_rows):
            end_index = row_index
            if row_index in merged_rows:
                while end_index + 1 < len(rendered_rows) and end_index + 1 in merged_rows:
                    end_index += 1
            rows_html = "".join(rendered_rows[row_index:end_index + 1])
            rendered_blocks.append(
                f"<table cellspacing=\"0\" cellpadding=\"0\" style=\"{'; '.join(table_styles)}\">{rows_html}</table>"
            )
            row_index = end_index + 1
        return rendered_blocks

    def _image_placeholder(self, element: ElementTree.Element) -> str:
        """Replace a picture/drawing with the fixed-size preview placeholder."""
        return self._placeholder_block("Здесь была картинка")

    @staticmethod
    def _formula_placeholder(_formula: str) -> str:
        """Replace a formula with the same fixed-size preview placeholder as images."""
        return WordDocumentService._placeholder_block("Здесь была формула")

    @staticmethod
    def _placeholder_block(label: str) -> str:
        """Render a small, fixed-size gray rectangle centered in the preview."""
        return (
            '<table align="center" width="190" height="56" cellspacing="0" cellpadding="0" '
            'style="border-collapse: collapse; margin-left: auto; margin-right: auto">'
            '<tr><td width="190" height="56" bgcolor="#e3e5e8" align="center" valign="middle" '
            'style="border: 1px solid #b8bdc6; color: #626873; padding: 18px 12px">'
            f"{label}</td></tr></table>"
        )

    @staticmethod
    def _border_style(side: str, border: ElementTree.Element) -> str:
        value = border.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "single")
        if value in {"nil", "none"}:
            return f"border-{side}: none"
        border_kind = {
            "dashed": "dashed",
            "dotted": "dotted",
            "double": "double",
            "dashDot": "dashed",
            "dashDotDot": "dashed",
            "single": "solid",
            "thick": "solid",
        }.get(value, "solid")
        size = border.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz", "4")
        width = int(size) / 8 if size.isdigit() else 0.5
        color = border.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color", "8c929b")
        if len(color) != 6 or not all(char in "0123456789abcdefABCDEF" for char in color):
            color = "8c929b"
        return f"border-{side}: {width:g}pt {border_kind} #{color}"

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _value(element: ElementTree.Element, attribute: str, default: str) -> str:
        return element.get(
            f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attribute}",
            default,
        )
