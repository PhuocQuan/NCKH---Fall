"""
Thư viện thuần Python (Pure Python) tạo tệp Microsoft Word (.docx) chuẩn OpenXML
Hỗ trợ đầy đủ Tiếng Việt Unicode UTF-8, định dạng tiêu đề, bảng biểu, danh sách, hộp ghi chú (callout) và khối code.
Không yêu cầu bất kỳ thư viện ngoài (zero-dependency).
"""

import html
import zipfile
from pathlib import Path


class DocxBuilder:
    def __init__(self, title="Document", author="FallGuard AI Research Team"):
        self.title = title
        self.author = author
        self.elements = []

    def add_title(self, text):
        escaped = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:pStyle w:val="Title"/>
            <w:jc w:val="center"/>
            <w:spacing w:before="360" w:after="180"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:b/>
              <w:sz w:val="48"/>
              <w:color w:val="1F4E79"/>
            </w:rPr>
            <w:t>{escaped}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_subtitle(self, text):
        escaped = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:jc w:val="center"/>
            <w:spacing w:before="100" w:after="300"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:i/>
              <w:sz w:val="26"/>
              <w:color w:val="595959"/>
            </w:rPr>
            <w:t>{escaped}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_heading_1(self, text):
        escaped = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:pStyle w:val="Heading1"/>
            <w:spacing w:before="360" w:after="140"/>
            <w:keepNext/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:b/>
              <w:sz w:val="34"/>
              <w:color w:val="1F4E79"/>
            </w:rPr>
            <w:t>{escaped}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_heading_2(self, text):
        escaped = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:pStyle w:val="Heading2"/>
            <w:spacing w:before="260" w:after="100"/>
            <w:keepNext/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:b/>
              <w:sz w:val="28"/>
              <w:color w:val="2E75B6"/>
            </w:rPr>
            <w:t>{escaped}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_heading_3(self, text):
        escaped = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:pStyle w:val="Heading3"/>
            <w:spacing w:before="180" w:after="80"/>
            <w:keepNext/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:b/>
              <w:sz w:val="24"/>
              <w:color w:val="1B365D"/>
            </w:rPr>
            <w:t>{escaped}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_paragraph(self, text, bold_prefix=None, italic=False, justify=True):
        jc_val = "both" if justify else "left"
        r_prefix = ""
        if bold_prefix:
            esc_pre = html.escape(bold_prefix)
            r_prefix = f"""<w:r>
              <w:rPr>
                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
                <w:b/>
                <w:sz w:val="24"/>
              </w:rPr>
              <w:t xml:space="preserve">{esc_pre} </w:t>
            </w:r>"""
        
        esc_text = html.escape(text)
        i_tag = "<w:i/>" if italic else ""
        xml = f"""<w:p>
          <w:pPr>
            <w:jc w:val="{jc_val}"/>
            <w:spacing w:before="60" w:after="100" w:line="300" w:lineRule="auto"/>
          </w:pPr>
          {r_prefix}
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              {i_tag}
              <w:sz w:val="24"/>
            </w:rPr>
            <w:t xml:space="preserve">{esc_text}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_bullet(self, text, bold_prefix=None, level=0):
        indent_left = 360 * (level + 1)
        r_prefix = ""
        if bold_prefix:
            esc_pre = html.escape(bold_prefix)
            r_prefix = f"""<w:r>
              <w:rPr>
                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
                <w:b/>
                <w:sz w:val="24"/>
              </w:rPr>
              <w:t xml:space="preserve">{esc_pre} </w:t>
            </w:r>"""
            
        esc_text = html.escape(text)
        xml = f"""<w:p>
          <w:pPr>
            <w:ind w:left="{indent_left}" w:hanging="240"/>
            <w:spacing w:before="40" w:after="60" w:line="280" w:lineRule="auto"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:sz w:val="24"/>
              <w:color w:val="2E75B6"/>
            </w:rPr>
            <w:t xml:space="preserve">● </w:t>
          </w:r>
          {r_prefix}
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
              <w:sz w:val="24"/>
            </w:rPr>
            <w:t xml:space="preserve">{esc_text}</w:t>
          </w:r>
        </w:p>"""
        self.elements.append(xml)

    def add_callout(self, text, title="LƯU Ý QUAN TRỌNG / NOTE"):
        esc_title = html.escape(title)
        esc_text = html.escape(text)
        xml = f"""<w:tbl>
          <w:tblPr>
            <w:tblW w:w="9600" w:type="dxa"/>
            <w:tblBorders>
              <w:top w:val="none"/>
              <w:left w:val="single" w:sz="36" w:space="0" w:color="1F4E79"/>
              <w:bottom w:val="none"/>
              <w:right w:val="none"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="140" w:type="dxa"/>
              <w:left w:w="240" w:type="dxa"/>
              <w:bottom w:w="140" w:type="dxa"/>
              <w:right w:w="240" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tr>
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="9600" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="F2F7FA"/>
              </w:tcPr>
              <w:p>
                <w:pPr>
                  <w:spacing w:before="60" w:after="40"/>
                </w:pPr>
                <w:r>
                  <w:rPr>
                    <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
                    <w:b/>
                    <w:sz w:val="24"/>
                    <w:color w:val="1F4E79"/>
                  </w:rPr>
                  <w:t>💡 {esc_title}</w:t>
                </w:r>
              </w:p>
              <w:p>
                <w:pPr>
                  <w:spacing w:before="40" w:after="60" w:line="280" w:lineRule="auto"/>
                </w:pPr>
                <w:r>
                  <w:rPr>
                    <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
                    <w:sz w:val="23"/>
                  </w:rPr>
                  <w:t>{esc_text}</w:t>
                </w:r>
              </w:p>
            </w:tc>
          </w:tr>
        </w:tbl>
        <w:p><w:pPr><w:spacing w:after="100"/></w:pPr></w:p>"""
        self.elements.append(xml)

    def add_code_block(self, code_text):
        esc_code = html.escape(code_text)
        lines = esc_code.split("\n")
        inner_paras = ""
        for line in lines:
            inner_paras += f"""<w:p>
              <w:pPr>
                <w:spacing w:before="20" w:after="20"/>
              </w:pPr>
              <w:r>
                <w:rPr>
                  <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>
                  <w:sz w:val="19"/>
                  <w:color w:val="24292E"/>
                </w:rPr>
                <w:t xml:space="preserve">{line}</w:t>
              </w:r>
            </w:p>"""

        xml = f"""<w:tbl>
          <w:tblPr>
            <w:tblW w:w="9600" w:type="dxa"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
              <w:left w:val="single" w:sz="18" w:space="0" w:color="2E75B6"/>
              <w:bottom w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
              <w:right w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="120" w:type="dxa"/>
              <w:left w:w="200" w:type="dxa"/>
              <w:bottom w:w="120" w:type="dxa"/>
              <w:right w:w="200" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tr>
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="9600" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="F6F8FA"/>
              </w:tcPr>
              {inner_paras}
            </w:tc>
          </w:tr>
        </w:tbl>
        <w:p><w:pPr><w:spacing w:after="100"/></w:pPr></w:p>"""
        self.elements.append(xml)

    def add_table(self, headers, rows):
        col_count = len(headers)
        total_width = 9600
        col_width = total_width // col_count

        hdr_xml = "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        for h in headers:
            esc_h = html.escape(str(h))
            hdr_xml += f"""<w:tc>
              <w:tcPr>
                <w:tcW w:w="{col_width}" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="1F4E79"/>
                <w:tcMar><w:top w:w="100" w:type="dxa"/><w:bottom w:w="100" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
              </w:tcPr>
              <w:p>
                <w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr>
                <w:r>
                  <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="23"/><w:color w:val="FFFFFF"/></w:rPr>
                  <w:t>{esc_h}</w:t>
                </w:r>
              </w:p>
            </w:tc>"""
        hdr_xml += "</w:tr>"

        rows_xml = ""
        for r_idx, row in enumerate(rows):
            bg_color = "F9FBFC" if r_idx % 2 == 1 else "FFFFFF"
            rows_xml += f"<w:tr>"
            for c_idx, cell in enumerate(row):
                esc_c = html.escape(str(cell))
                jc_align = "left" if c_idx == 0 or len(esc_c) > 20 else "center"
                rows_xml += f"""<w:tc>
                  <w:tcPr>
                    <w:tcW w:w="{col_width}" w:type="dxa"/>
                    <w:shd w:val="clear" w:color="auto" w:fill="{bg_color}"/>
                    <w:tcMar><w:top w:w="80" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
                  </w:tcPr>
                  <w:p>
                    <w:pPr><w:jc w:val="{jc_align}"/><w:spacing w:before="40" w:after="40"/></w:pPr>
                    <w:r>
                      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="22"/></w:rPr>
                      <w:t>{esc_c}</w:t>
                    </w:r>
                  </w:p>
                </w:tc>"""
            rows_xml += "</w:tr>"

        xml = f"""<w:tbl>
          <w:tblPr>
            <w:tblW w:w="9600" w:type="dxa"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="8" w:space="0" w:color="1F4E79"/>
              <w:left w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>
              <w:bottom w:val="single" w:sz="8" w:space="0" w:color="1F4E79"/>
              <w:right w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>
              <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E1E4E8"/>
              <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E1E4E8"/>
            </w:tblBorders>
          </w:tblPr>
          {hdr_xml}
          {rows_xml}
        </w:tbl>
        <w:p><w:pPr><w:spacing w:after="120"/></w:pPr></w:p>"""
        self.elements.append(xml)

    def add_page_break(self):
        self.elements.append("""<w:p><w:r><w:br w:type="page"/></w:r></w:p>""")

    def save(self, filepath):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        body_content = "\n".join(self.elements)

        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {body_content}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""

        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

        root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

        doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="24"/>
        <w:szCs w:val="24"/>
        <w:lang w:val="vi-VN"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
</w:styles>"""

        with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as docx:
            docx.writestr("[Content_Types].xml", content_types)
            docx.writestr("_rels/.rels", root_rels)
            docx.writestr("word/_rels/document.xml.rels", doc_rels)
            docx.writestr("word/styles.xml", styles_xml)
            docx.writestr("word/document.xml", document_xml.encode("utf-8"))

        print(f"[DocxBuilder] Created document: {path} ({path.stat().st_size} bytes)")
        return str(path)
