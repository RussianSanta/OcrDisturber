"""Read Word documents and convert paragraph formatting for the preview."""

from html import escape
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


class WordDocumentService:
    """Load a document into memory and extract formatted DOCX paragraphs."""

    _WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def read(self, file_path: str) -> tuple[bytes, list[str]]:
        """Return source bytes and paragraph HTML suitable for QTextEdit."""
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
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{self._WORD_NS}p"):
            properties = paragraph.find(f"{self._WORD_NS}pPr")
            styles: list[str] = []
            if properties is not None:
                alignment = properties.find(f"{self._WORD_NS}jc")
                if alignment is not None:
                    value = self._value(alignment, "val", "left")
                    styles.append(f"text-align: {'justify' if value == 'both' else value}")
                indent = properties.find(f"{self._WORD_NS}ind")
                if indent is not None:
                    for attribute, css_property in (("left", "margin-left"), ("right", "margin-right"), ("firstLine", "text-indent")):
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

            content: list[str] = []
            for run in paragraph.iter(f"{self._WORD_NS}r"):
                run_properties = run.find(f"{self._WORD_NS}rPr")
                run_styles: list[str] = []
                if run_properties is not None:
                    if run_properties.find(f"{self._WORD_NS}b") is not None:
                        run_styles.append("font-weight: bold")
                    if run_properties.find(f"{self._WORD_NS}i") is not None:
                        run_styles.append("font-style: italic")
                    if run_properties.find(f"{self._WORD_NS}u") is not None:
                        run_styles.append("text-decoration: underline")
                    size = run_properties.find(f"{self._WORD_NS}sz")
                    if size is not None and (value := size.get(f"{self._WORD_NS}val", "")).isdigit():
                        run_styles.append(f"font-size: {int(value) / 2:g}pt")
                    fonts = run_properties.find(f"{self._WORD_NS}rFonts")
                    if fonts is not None and (font := fonts.get(f"{self._WORD_NS}ascii")):
                        run_styles.append(f"font-family: '{escape(font)}'")
                    color = run_properties.find(f"{self._WORD_NS}color")
                    if color is not None and (value := color.get(f"{self._WORD_NS}val", "")):
                        if len(value) == 6 and all(char in "0123456789abcdefABCDEF" for char in value):
                            run_styles.append(f"color: #{value}")

                run_content: list[str] = []
                for node in run.iter():
                    if node.tag == f"{self._WORD_NS}t" and node.text:
                        run_content.append(escape(node.text))
                    elif node.tag == f"{self._WORD_NS}tab":
                        run_content.append("&#9;")
                    elif node.tag == f"{self._WORD_NS}br":
                        run_content.append("<br>")
                fragment = "".join(run_content)
                if run_styles:
                    fragment = f"<span style=\"{'; '.join(run_styles)}\">{fragment}</span>"
                content.append(fragment)

            style_attribute = f" style=\"{'; '.join(styles)}\"" if styles else ""
            paragraphs.append(f"<p{style_attribute}>{''.join(content) or '&nbsp;'}</p>")
        return data, paragraphs or ["<p></p>"]

    @staticmethod
    def _value(element: ElementTree.Element, attribute: str, default: str) -> str:
        """Get a Word XML attribute by its local name."""
        return element.get(f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attribute}", default)
