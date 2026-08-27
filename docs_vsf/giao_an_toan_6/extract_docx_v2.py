# -*- coding: utf-8 -*-
"""
Enhanced docx extraction: captures math formulas, tables, textboxes, and formats to clean Markdown.
"""
import sys, re, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

_HERE = Path(__file__).resolve().parent
DOCX_FOLDER = _HERE
OUTPUT = _HERE / "docx_extracted_v2.json"

import docx
from lxml import etree

# Namespaces for XML parsing
NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'v': 'urn:schemas-microsoft-com:vml',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
}


# ============================================================================
# MATH FORMULA EXTRACTOR (OMML → LaTeX)
# ============================================================================

def _omml_to_latex(elem):
    """Convert OMML (m:oMath) to text representation — captures all math content."""
    if elem is None:
        return ''
    
    tag = etree.QName(elem).localname if elem.tag else ''
    m_ns = NSMAP['m']
    w_ns = NSMAP['w']
    
    # TEXT: m:t or w:t
    if tag == 't':
        return (elem.text or '')
    
    # RUN: m:r — contains m:t
    if tag == 'r':
        t = elem.find(f'{{{m_ns}}}t')
        if t is not None and t.text:
            return t.text
        t = elem.find(f'{{{w_ns}}}t')
        if t is not None and t.text:
            return t.text
        return ''
    
    # FRACTION: m:f → m:num / m:den
    if tag == 'f':
        num = elem.find(f'{{{m_ns}}}num')
        den = elem.find(f'{{{m_ns}}}den')
        all_texts = [c.text for c in elem.iter() if c.text and len(c.text.strip()) > 0]
        if len(all_texts) >= 2:
            return f"({all_texts[0]})/({all_texts[1]})"
        num_str = _omml_to_latex(num) if num is not None else ''
        den_str = _omml_to_latex(den) if den is not None else ''
        if num_str and den_str:
            return f"({num_str})/({den_str})"
        return f"({''.join(all_texts)})" if all_texts else ''
    
    # SUPERSCRIPT: m:sSup → m:e ^ m:sup
    if tag == 'sSup':
        e = elem.find(f'{{{m_ns}}}e')
        sup = elem.find(f'{{{m_ns}}}sup')
        e_str = _omml_to_latex(e) if e is not None else ''
        sup_str = _omml_to_latex(sup) if sup is not None else ''
        return f"{e_str}^{{{sup_str}}}"
    
    # SUBSCRIPT: m:sSub → m:e _ m:sub
    if tag == 'sSub':
        e = elem.find(f'{{{m_ns}}}e')
        sub = elem.find(f'{{{m_ns}}}sub')
        e_str = _omml_to_latex(e) if e is not None else ''
        sub_str = _omml_to_latex(sub) if sub is not None else ''
        return f"{e_str}_{{{sub_str}}}"
    
    # RADICAL (SQRT): m:rad → \sqrt[m:deg]{m:e}
    if tag == 'rad':
        deg = elem.find(f'{{{m_ns}}}deg')
        e = elem.find(f'{{{m_ns}}}e')
        deg_str = _omml_to_latex(deg) if deg is not None else ''
        e_str = _omml_to_latex(e) if e is not None else ''
        if deg_str:
            return f"\\sqrt[{deg_str}]{{{e_str}}}"
        return f"\\sqrt{{{e_str}}}"
    
    # NARY (SUM/INT/PROD): m:nary → \sum_{sub}^{sup}{e}
    if tag == 'nary':
        sub = elem.find(f'{{{m_ns}}}sub')
        sup = elem.find(f'{{{m_ns}}}sup')
        e = elem.find(f'{{{m_ns}}}e')
        sub_str = _omml_to_latex(sub) if sub is not None else ''
        sup_str = _omml_to_latex(sup) if sup is not None else ''
        e_str = _omml_to_latex(e) if e is not None else ''
        return f"\\int_{{{sub_str}}}^{{{sup_str}}} {e_str}"
    
    # DELIMITER: m:d → ( ... )
    if tag == 'd':
        e = elem.find(f'{{{m_ns}}}e')
        e_str = _omml_to_latex(e) if e is not None else ''
        return f"({e_str})"
    
    # BOX / GROUP CHR / FUNC
    if tag in ('box', 'groupChr', 'func', 'e', 'num', 'den', 'sup', 'sub', 'deg'):
        parts = []
        for child in elem:
            child_text = _omml_to_latex(child)
            if child_text:
                parts.append(child_text)
        return ''.join(parts)
    
    # DEFAULT: Iterate all children
    parts = []
    for child in elem:
        child_text = _omml_to_latex(child)
        if child_text:
            parts.append(child_text)
    if parts:
        return ''.join(parts)
    
    all_texts = [c.text for c in elem.iter() if c.text and len(c.text.strip()) > 0]
    return ''.join(all_texts)


def extract_math_text_hybrid(para) -> str:
    """Iterate through XML children in document order and extract text and math."""
    if not hasattr(para, '_element'):
        return para.text or ''
    
    xml_str = para._element.xml
    if 'm:oMath' not in xml_str and 'm:oMathPara' not in xml_str:
        return para.text or ''
    
    m_ns = NSMAP['m']
    w_ns = NSMAP['w']
    
    root = para._element
    result_parts = []
    
    for child in root:
        tag = etree.QName(child).localname if child.tag else ''
        
        # Word text run
        if tag == 'r':
            texts = child.findall(f'.//{{{w_ns}}}t')
            for t in texts:
                if t.text:
                    result_parts.append(t.text)
        
        # Math run or container
        elif tag in ('oMath', 'oMathPara'):
            latex = _omml_to_latex(child)
            if latex and latex.strip():
                latex_clean = latex.strip()
                # If already starts with $, don't double wrap
                if not latex_clean.startswith('$'):
                    result_parts.append(f" ${latex_clean}$ ")
                else:
                    result_parts.append(f" {latex_clean} ")
        
        # Hyperlink
        elif tag == 'hyperlink':
            for r in child.findall(f'.//{{{w_ns}}}t'):
                if r.text:
                    result_parts.append(r.text)
    
    full_text = ''.join(result_parts).strip()
    return full_text if full_text else (para.text or '')


# ============================================================================
# MARKDOWN FORMATTERS
# ============================================================================

def format_paragraph_to_markdown(text: str, style: str = "") -> str:
    """Convert raw extracted paragraph to clean, structured Markdown."""
    if not text:
        return ""
    l = text.strip()
    if not l:
        return ""
    
    # 1. Làm sạch nháy thừa quanh ký hiệu math: “$∈$” -> $∈$, "$∈$" -> $∈$
    l = re.sub(r'["“”](\$[^\$]+\$)["“”]', r'\1', l)
    l = re.sub(r'["“”]\s*([∈∉≤≥≠±×÷])\s*["“”]', r'$\1$', l)
    l = re.sub(r'\$\s*\$', '', l) # bỏ rỗng
    
    # 2. Tiêu đề cấp 1 lớn của bài học (TIẾT 1, TIẾT 2..., BÀI 1...)
    if re.match(r"^TIẾT\s+\d+.*:", l, re.IGNORECASE) or re.match(r"^BÀI\s+\d+.*:", l, re.IGNORECASE):
        return f"\n## {l}\n"
    
    # 3. Đề mục lớn số La Mã: I. MỤC TIÊU, II. THIẾT BỊ DẠY HỌC, III. TIẾN TRÌNH DẠY HỌC, IV. KẾ HOẠCH ĐÁNH GIÁ, V. HỒ SƠ DẠY HỌC
    if re.match(r"^(I|II|III|IV|V|VI)\.\s+[A-ZÀ-Ỹ\s]+", l):
        return f"\n## {l}\n"
    
    # 4. Hoạt động lớn: A. HOẠT ĐỘNG KHỞI ĐỘNG, B. HÌNH THÀNH KIẾN THỨC MỚI, C. HOẠT ĐỘNG LUYỆN TẬP, D. HOẠT ĐỘNG VẬN DỤNG
    if re.match(r"^(A|B|C|D|E)\.\s+[A-ZÀ-Ỹ\s]+", l):
        return f"\n### {l}\n"
    
    # 5. Các mục con có số: 1. Kiến thức, 2. Năng lực, 3. Phẩm chất, 1. Giáo viên, 2. Học sinh, Hoạt động 1: ...
    if re.match(r"^(Hoạt động\s+\d+:|HĐKP\d*:|Luyện tập\s+\d*:|Thực hành\s+\d*:|Vận dụng\s+\d*:)", l, re.IGNORECASE):
        return f"\n#### {l}\n"
    if re.match(r"^\d+\.\s+(Kiến thức|Năng lực|Phẩm chất|Giáo viên|Học sinh)", l, re.IGNORECASE) or re.match(r"^\d+\s*[-–]\s*(GV|HS)\s*:", l, re.IGNORECASE):
        return f"\n#### {l}\n"
        
    # 5b. Các nhóm năng lực / phẩm chất con: Năng lực riêng, Năng lực chung, Phẩm chất
    if re.match(r"^[-\+*•\s]*(Năng lực riêng|Năng lực chung|Phẩm chất):?", l, re.IGNORECASE):
        clean_head = re.sub(r'^[-\+*•\s]+', '', l).strip()
        return f"\n- **{clean_head}**"

    # 6. Các tiểu mục: a) Mục tiêu, b) Nội dung, c) Sản phẩm, d) Tổ chức thực hiện (hoặc a. Mục tiêu, b. Nội dung...)
    if re.match(r"^[a-d][\.\)]\s*(Mục tiêu|Mục đích|Nội dung|Sản phẩm|Tổ chức thực hiện):?", l, re.IGNORECASE):
        return f"\n- **{l}**"
        
    # 7. Các bước thực hiện: Bước 1: Chuyển giao..., Bước 2: Thực hiện...
    if re.match(r"^Bước\s+\d+:", l, re.IGNORECASE):
        return f"\n  - **{l}**"
        
    # 8. Gạch đầu dòng phụ (+) -> thụt lề
    if l.startswith("+ "):
        return f"  - {l[2:].strip()}"
        
    # 9. Gạch đầu dòng chính (-)
    if l.startswith("- ") or l.startswith("• "):
        return f"- {l[2:].strip()}"
        
    return l


def format_table(table, table_index):
    """Convert docx table to standard Markdown table format."""
    rows_list = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            # Lấy text từng đoạn trong ô, nối bằng khoảng trắng hoặc dấu gạch
            paras = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
            c_text = ' <br/> '.join(paras)
            c_text = c_text.replace('|', '&#124;')
            c_text = re.sub(r'["“”](\$[^\$]+\$)["“”]', r'\1', c_text)
            cells.append(c_text)
        # Bắt buộc có dấu | ở đầu và cuối dòng để Markdown nhận diện là bảng
        rows_list.append('| ' + ' | '.join(cells) + ' |')
    
    if not rows_list:
        return ''
    
    header = rows_list[0]
    col_count = len(table.rows[0].cells) if table.rows else 0
    separator = '| ' + ' | '.join(['---'] * col_count) + ' |'
    body = '\n'.join(rows_list[1:]) if len(rows_list) > 1 else ''
    
    return f'\n\n{header}\n{separator}\n{body}\n\n'


def extract_textboxes_from_xml(xml_str: str) -> str:
    """Find w:txbxContent elements in paragraph XML."""
    if 'txbxContent' not in xml_str:
        return ''
    
    root = etree.fromstring(xml_str.encode())
    texts = []
    for tbx in root.iter(f'{{{NSMAP["w"]}}}txbxContent'):
        for t in tbx.iter(f'{{{NSMAP["w"]}}}t'):
            if t.text:
                texts.append(t.text)
    
    if texts:
        return '\n'.join(texts)
    return ''


def extract_images_from_xml(xml_str: str) -> list[str]:
    """Find image references in paragraph XML."""
    if 'wp:inline' not in xml_str and 'wp:anchor' not in xml_str and 'v:shape' not in xml_str:
        return []
    
    images = []
    inline_count = xml_str.count('wp:inline')
    anchor_count = xml_str.count('wp:anchor')
    total = inline_count + anchor_count
    
    if total > 0:
        root = etree.fromstring(xml_str.encode())
        for desc in root.iter(f'{{{NSMAP["wp"]}}}docPr'):
            name = desc.get('name', '') if desc is not None else ''
            descr = desc.get('descr', '') if desc is not None else ''
            if name or descr:
                images.append(f'*[Hình minh họa: {name} - {descr}]*')
        
        if not images:
            images.append(f'*[Hình minh họa]*')
    
    return images


# ============================================================================
# MAIN EXTRACTION
# ============================================================================

def extract_lessons_enhanced(path):
    """Extract lessons with math, tables, textboxes preserved in clean Markdown."""
    doc = docx.Document(path)
    table_count = len(doc.tables)
    
    body = doc.element.body
    current_para_idx = -1
    table_idx = 0
    tables_between_paras: dict[int, int] = {}
    
    for child in body:
        local = etree.QName(child).localname if child.tag else ''
        if local == 'p':
            current_para_idx += 1
        elif local == 'tbl':
            if table_idx < table_count:
                tables_between_paras[current_para_idx] = table_idx
                table_idx += 1
    
    lessons = []
    current_lesson = None
    current_content_parts = []
    
    def _flush_lesson():
        nonlocal current_lesson, current_content_parts
        if current_lesson:
            raw_content = '\n'.join(current_content_parts)
            # Gộp khoảng trắng thừa
            clean_content = re.sub(r'\n{3,}', '\n\n', raw_content).strip()
            current_lesson['content'] = clean_content
            lessons.append(current_lesson)
            current_content_parts = []
    
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        style = para.style.name if para.style else ''
        xml_str = para._element.xml if hasattr(para, '_element') else ''
        
        # Check if a table sits AFTER this paragraph
        if i in tables_between_paras:
            tbl_idx = tables_between_paras[i]
            if tbl_idx < table_count:
                table_md = format_table(doc.tables[tbl_idx], tbl_idx + 1)
                if table_md:
                    current_content_parts.append(table_md)
        
        # Extract math formula from XML
        math_content = extract_math_text_hybrid(para)
        
        # Extract textboxes
        textbox_content = extract_textboxes_from_xml(xml_str)
        
        # Extract images
        images = extract_images_from_xml(xml_str)
        
        if 'heading 1' == style.lower() and text:
            if current_lesson and not current_content_parts:
                current_lesson['title'] = current_lesson['title'] + ' | ' + text
            else:
                _flush_lesson()
                current_lesson = {
                    'title': text,
                    'index': i,
                }
                current_content_parts = []
        elif current_lesson and text:
            display_text = math_content or text
            formatted = format_paragraph_to_markdown(display_text, style)
            if formatted:
                current_content_parts.append(formatted)
        
        if textbox_content:
            current_content_parts.append(f"\n> **Ghi chú:** {textbox_content}\n")
        
        for img in images:
            current_content_parts.append(f"\n{img}\n")
    
    _flush_lesson()
    
    return {
        'file': str(path.name),
        'total_paragraphs': len(doc.paragraphs),
        'lessons': lessons,
        'stats': {
            'tables': table_count,
            'math_paras': len([p for p in doc.paragraphs if 'm:oMath' in (p._element.xml if hasattr(p, '_element') else '')]),
        }
    }


def main():
    files = [
        DOCX_FOLDER / "KHBD Toan 6 (CTST)-Ki.docx",
        DOCX_FOLDER / "KHBD Toan 6 (CTST)-KII.docx",
    ]
    
    result = {}
    for path in files:
        if not path.exists():
            print(f"[ERROR] Not found: {path}")
            continue
        name = "HK1" if "Ki.docx" in path.name else "HK2"
        print(f"[INFO] Processing {name}: {path.name}...")
        result[name] = extract_lessons_enhanced(path)
        print(f"  -> {len(result[name]['lessons'])} lessons / {result[name]['stats']['tables']} tables / {result[name]['stats']['math_paras']} math paras")
    
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[SUCCESS] Saved clean Markdown to {OUTPUT}")


if __name__ == "__main__":
    main()