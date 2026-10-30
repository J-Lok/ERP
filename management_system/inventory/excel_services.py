"""
Excel Import / Export services for Stock inventory, supporting embedded images and photos.
"""
import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
import requests
from PIL import Image as PILImage
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter, coordinate_to_tuple
from openpyxl.drawing.image import Image as OpenpyxlImage
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils import timezone


COLUMN_SYNONYMS = {
    # item_code
    'item_code': 'item_code',
    'item code': 'item_code',
    'itemcode': 'item_code',
    'code': 'item_code',
    'code_article': 'item_code',
    'code article': 'item_code',
    'code_produit': 'item_code',
    'code produit': 'item_code',
    'reference': 'item_code',
    'référence': 'item_code',
    'ref': 'item_code',
    'sku': 'item_code',

    # name
    'name': 'name',
    'item_name': 'name',
    'item name': 'name',
    'itemname': 'name',
    'nom': 'name',
    'nom_article': 'name',
    'nom article': 'name',
    'designation': 'name',
    'désignation': 'name',
    'libelle': 'name',
    'libellé': 'name',
    'titre': 'name',

    # category
    'category': 'category',
    'category_name': 'category',
    'categorie': 'category',
    'catégorie': 'category',

    # description
    'description': 'description',
    'details': 'description',
    'détails': 'description',

    # quantity
    'quantity': 'quantity',
    'qty': 'quantity',
    'quantite': 'quantity',
    'quantité': 'quantity',
    'qte': 'quantity',
    'qté': 'quantity',
    'stock': 'quantity',

    # unit
    'unit': 'unit',
    'unite': 'unit',
    'unité': 'unit',
    'uom': 'unit',

    # cost_price
    'cost_price': 'cost_price',
    'cost price': 'cost_price',
    'cost': 'cost_price',
    'unit_price': 'cost_price',
    'unit price': 'cost_price',
    'prix_achat': 'cost_price',
    'prix d\'achat': 'cost_price',
    'prix d achat': 'cost_price',
    'prix achat': 'cost_price',
    'cout': 'cost_price',
    'coût': 'cost_price',

    # selling_price
    'selling_price': 'selling_price',
    'selling price': 'selling_price',
    'sale_price': 'selling_price',
    'prix_vente': 'selling_price',
    'prix de vente': 'selling_price',
    'prix vente': 'selling_price',

    # reorder_level
    'reorder_level': 'reorder_level',
    'reorder level': 'reorder_level',
    'reorder': 'reorder_level',
    'seuil_reapprovisionnement': 'reorder_level',
    'seuil de réapprovisionnement': 'reorder_level',
    'seuil_alerte': 'reorder_level',
    'seuil alerte': 'reorder_level',
    'alerte': 'reorder_level',

    # supplier_name
    'supplier_name': 'supplier_name',
    'supplier name': 'supplier_name',
    'supplier': 'supplier_name',
    'fournisseur': 'supplier_name',
    'nom_fournisseur': 'supplier_name',
    'nom fournisseur': 'supplier_name',

    # supplier_contact
    'supplier_contact': 'supplier_contact',
    'supplier contact': 'supplier_contact',
    'contact_fournisseur': 'supplier_contact',
    'contact fournisseur': 'supplier_contact',

    # location
    'location': 'location',
    'emplacement': 'location',
    'entrepot': 'location',
    'entrepôt': 'location',
    'stockage': 'location',

    # is_marketplace_visible
    'is_marketplace_visible': 'is_marketplace_visible',
    'marketplace_visible': 'is_marketplace_visible',
    'marketplace visible': 'is_marketplace_visible',
    'visible_marketplace': 'is_marketplace_visible',
    'visible sur marketplace': 'is_marketplace_visible',

    # photo / image
    'photo': 'image',
    'photos': 'image',
    'image': 'image',
    'images': 'image',
    'picture': 'image',
    'pictures': 'image',
    'img': 'image',
    'image_url': 'image',
    'photo_url': 'image',
}


def normalize_column_name(col_name):
    """Normalize any column header to standard field name."""
    if not col_name:
        return ''
    clean = str(col_name).strip().lower().replace('\n', ' ')
    clean_snake = clean.replace(' ', '_').replace('-', '_')
    if clean_snake in COLUMN_SYNONYMS:
        return COLUMN_SYNONYMS[clean_snake]
    if clean in COLUMN_SYNONYMS:
        return COLUMN_SYNONYMS[clean]
    return clean_snake


def extract_excel_images(file_bytes):
    """
    Extracts all images embedded in an Excel (.xlsx) file.
    Returns:
        images_by_row: {excel_row_num (1-indexed): bytes}
        images_by_cell: {(excel_row_num, excel_col_num): bytes}
    """
    images_by_row = {}
    images_by_cell = {}

    # 1. Native openpyxl drawings (covers standard inserted images & our exports)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active or wb.worksheets[0]
        for img in getattr(ws, '_images', []):
            try:
                row_idx = None
                col_idx = None
                anchor = getattr(img, 'anchor', None)
                if anchor is not None:
                    _from = getattr(anchor, '_from', None)
                    if _from is not None and hasattr(_from, 'row'):
                        try:
                            # _from.row is 0-indexed in openpyxl, convert to 1-indexed Excel row
                            row_idx = int(_from.row) + 1
                            if hasattr(_from, 'col'):
                                col_idx = int(_from.col) + 1
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(anchor, str):
                        try:
                            r, c = coordinate_to_tuple(anchor)
                            row_idx, col_idx = r, c
                        except Exception:
                            pass

                if row_idx is not None:
                    raw_data = img._data()
                    if raw_data:
                        if col_idx is not None:
                            images_by_cell[(row_idx, col_idx)] = raw_data
                        if row_idx not in images_by_row:
                            images_by_row[row_idx] = raw_data
            except Exception:
                continue
    except Exception:
        pass

    # 2. Modern Excel 365 "Place in Cell" (DISPIMG in xl/cellimages.xml)
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            names = z.namelist()
            if 'xl/cellimages.xml' in names and 'xl/_rels/cellimages.xml.rels' in names:
                rels_tree = ET.fromstring(z.read('xl/_rels/cellimages.xml.rels'))
                rel_map = {}
                for rel in rels_tree:
                    r_id = rel.get('Id')
                    target = rel.get('Target')
                    if r_id and target:
                        if target.startswith('/'):
                            target = target[1:]
                        elif not target.startswith('xl/'):
                            target = 'xl/' + target
                        rel_map[r_id] = target

                ci_tree = ET.fromstring(z.read('xl/cellimages.xml'))
                id_to_target = {}
                for cell_img in ci_tree.findall('.//{http://schemas.microsoft.com/office/spreadsheetml/2020/pivotNov2020}cellImage'):
                    pic = cell_img.find('.//{http://schemas.microsoft.com/office/drawing/2010/main}pic')
                    if pic is not None:
                        blip = pic.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                        nv_pic_pr = pic.find('.//{http://schemas.microsoft.com/office/drawing/2010/main}nvPicPr')
                        cNvPr = nv_pic_pr.find('.//{http://schemas.microsoft.com/office/drawing/2010/main}cNvPr') if nv_pic_pr is not None else None
                        img_id = cNvPr.get('name') if cNvPr is not None else None
                        r_embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') if blip is not None else None
                        if img_id and r_embed in rel_map:
                            id_to_target[img_id] = rel_map[r_embed]

                sheet_names = [n for n in names if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
                for s_name in sheet_names:
                    sheet_tree = ET.fromstring(z.read(s_name))
                    for c in sheet_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                        cell_ref = c.get('r')
                        f = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f')
                        f_text = f.text if f is not None else ''
                        if f_text and 'DISPIMG' in f_text:
                            m = re.search(r'DISPIMG\("([^"]+)"', f_text)
                            if m:
                                img_id = m.group(1)
                                target_file = id_to_target.get(img_id)
                                if target_file and target_file in names:
                                    img_data = z.read(target_file)
                                    try:
                                        row_idx, col_idx = coordinate_to_tuple(cell_ref)
                                        images_by_cell[(row_idx, col_idx)] = img_data
                                        if row_idx not in images_by_row:
                                            images_by_row[row_idx] = img_data
                                    except Exception:
                                        pass
    except Exception:
        pass

    return images_by_row, images_by_cell


def get_image_for_row(row_num, row_data, photo_col_idx, images_by_row, images_by_cell):
    """
    Finds image bytes for a row by checking:
    1. Embedded image at (row_num, photo_col_idx)
    2. Embedded image anywhere on row_num
    3. URL or base64 in row_data['image']
    """
    # 1. Embedded image in specific photo column
    if photo_col_idx and (row_num, photo_col_idx) in images_by_cell:
        return images_by_cell[(row_num, photo_col_idx)]

    # 2. Embedded image on this row
    if row_num in images_by_row:
        return images_by_row[row_num]

    # 3. Text in 'image' column
    cell_val = row_data.get('image')
    if cell_val is not None:
        val = str(cell_val).strip()
        # URL
        if val.startswith(('http://', 'https://')):
            try:
                resp = requests.get(val, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if resp.status_code == 200:
                    return resp.content
            except Exception:
                pass
        # Base64
        if val.startswith('data:image/') and ';base64,' in val:
            try:
                import base64
                _, b64data = val.split(';base64,', 1)
                return base64.b64decode(b64data)
            except Exception:
                pass

    return None


def process_image_bytes(img_bytes, item_code):
    """
    Validates, optimizes, and prepares an image for saving to Django's ImageField.
    Returns: (filename, ContentFile) or None
    """
    if not img_bytes:
        return None
    try:
        pil_img = PILImage.open(io.BytesIO(img_bytes))
        fmt = (pil_img.format or 'JPEG').upper()
        if fmt not in ('JPEG', 'PNG', 'WEBP', 'GIF', 'BMP'):
            fmt = 'PNG'
        ext = 'jpg' if fmt == 'JPEG' else fmt.lower()

        # Resize if oversized (> 1600px)
        max_dim = 1600
        if pil_img.width > max_dim or pil_img.height > max_dim:
            pil_img.thumbnail((max_dim, max_dim), PILImage.Resampling.LANCZOS)
            out_buf = io.BytesIO()
            save_format = 'PNG' if ext == 'png' else 'JPEG'
            if save_format == 'JPEG' and pil_img.mode in ('RGBA', 'P', 'LA'):
                pil_img = pil_img.convert('RGB')
            pil_img.save(out_buf, format=save_format, quality=85)
            img_bytes = out_buf.getvalue()

        clean_code = slugify(str(item_code)) or 'product'
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:6]
        filename = f"{clean_code}_{timestamp}_{random_suffix}.{ext}"

        return filename, ContentFile(img_bytes)
    except Exception:
        return None


def get_stock_image_bytes(stock):
    """Safely retrieves image bytes from a Stock instance."""
    if not stock.image:
        return None

    # 1. Direct FieldFile.open()
    try:
        stock.image.open('rb')
        data = stock.image.read()
        stock.image.close()
        if data:
            return data
    except Exception:
        pass

    # 2. Local filesystem path
    try:
        if hasattr(stock.image, 'path') and stock.image.path:
            import os
            if os.path.exists(stock.image.path):
                with open(stock.image.path, 'rb') as f:
                    return f.read()
    except Exception:
        pass

    # 3. URL for remote storage (Cloudinary, S3, etc.)
    try:
        if hasattr(stock.image, 'url') and stock.image.url:
            url = stock.image.url
            if url.startswith(('http://', 'https://')):
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    return res.content
    except Exception:
        pass

    return None


def generate_stock_export_excel(stocks):
    """
    Generates an Excel workbook containing all stocks with embedded photo thumbnails.
    Returns bytes of the .xlsx file.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Stock Data'

    headers = [
        'Photo',
        'Item Code',
        'Name',
        'Category',
        'Description',
        'Quantity',
        'Unit',
        'Cost Price',
        'Selling Price',
        'Total Value',
        'Reorder Level',
        'Supplier Name',
        'Supplier Contact',
        'Location',
        'Marketplace Visible',
        'Last Restocked',
        'Needs Reorder',
        'Created By',
        'Created At',
    ]

    ws.append(headers)

    # Styles
    header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    data_font = Font(name='Segoe UI', size=10)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    right_align = Alignment(horizontal='right', vertical='center')

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws.row_dimensions[1].height = 28
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    image_streams = []  # Keep references open until workbook is saved

    row_idx = 2
    for stock in stocks:
        has_image = False
        img_bytes = get_stock_image_bytes(stock)

        if img_bytes:
            try:
                pil_img = PILImage.open(io.BytesIO(img_bytes))
                if pil_img.mode in ('RGBA', 'P', 'LA'):
                    # Keep PNG for transparency
                    pil_img = pil_img.convert('RGBA')
                else:
                    pil_img = pil_img.convert('RGB')

                # Thumbnail to fit 65x50 px box
                pil_img.thumbnail((65, 50), PILImage.Resampling.LANCZOS)
                thumb_buf = io.BytesIO()
                pil_img.save(thumb_buf, format='PNG')
                thumb_buf.seek(0)
                image_streams.append(thumb_buf)

                ox_img = OpenpyxlImage(thumb_buf)
                ox_img.width = pil_img.width
                ox_img.height = pil_img.height

                cell_ref = f'A{row_idx}'
                ws.add_image(ox_img, cell_ref)
                has_image = True
            except Exception:
                pass

        supplier_name = stock.supplier.name if getattr(stock, 'supplier', None) else ''
        supplier_contact = (stock.supplier.contact_person or stock.supplier.email or stock.supplier.phone) if getattr(stock, 'supplier', None) else ''

        row_data = [
            '',  # Column A is Photo
            stock.item_code,
            stock.name,
            stock.category.name if stock.category else '',
            stock.description or '',
            stock.quantity,
            stock.get_unit_display(),
            float(stock.cost_price),
            float(stock.selling_price),
            float(stock.total_value),
            stock.reorder_level,
            supplier_name,
            supplier_contact,
            stock.location or '',
            'Yes' if stock.is_marketplace_visible else 'No',
            stock.last_restocked.strftime('%Y-%m-%d') if stock.last_restocked else '',
            'Yes' if stock.needs_reorder else 'No',
            stock.created_by.get_full_name() if stock.created_by else '',
            stock.created_at.strftime('%Y-%m-%d %H:%M') if stock.created_at else '',
        ]

        ws.append(row_data)

        # Style data row
        ws.row_dimensions[row_idx].height = 55 if has_image else 24

        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border

            # Specific column alignments
            if col_idx in (1, 2, 7, 15, 16, 17, 19):  # Photo, Code, Unit, Yes/No, Dates
                cell.alignment = center_align
            elif col_idx in (6, 8, 9, 10, 11):  # Numbers & Currency
                cell.alignment = right_align
            else:
                cell.alignment = left_align

        row_idx += 1

    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 14  # Photo column
    for col_idx in range(2, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row in range(1, row_idx):
            val = ws.cell(row=row, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generate_stock_template_excel():
    """
    Generates an Excel workbook template for stock import, including Photo column.
    Returns bytes of the .xlsx file.
    """
    wb = openpyxl.Workbook()

    # Sheet 1: Template
    ws = wb.active
    ws.title = 'Template'

    headers = [
        'Photo',
        'item_code',
        'name',
        'category',
        'description',
        'quantity',
        'unit',
        'cost_price',
        'selling_price',
        'reorder_level',
        'supplier_name',
        'supplier_contact',
        'location',
        'is_marketplace_visible',
    ]
    ws.append(headers)

    sample_row = [
        '',  # Photo (user can insert image or paste URL)
        'ITEM-001',
        'Sample Item Name',
        'Electronics',
        'Sample product description',
        100,
        'pcs',
        10.50,
        15.99,
        20,
        'Sample Supplier Inc.',
        'contact@supplier.com',
        'Warehouse A, Shelf B2',
        'true',
    ]
    ws.append(sample_row)

    # Styles
    header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center')
    data_font = Font(name='Segoe UI', size=10)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    right_align = Alignment(horizontal='right', vertical='center')

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 50

    for col_idx in range(1, len(headers) + 1):
        h_cell = ws.cell(row=1, column=col_idx)
        h_cell.font = header_font
        h_cell.fill = header_fill
        h_cell.alignment = header_align

        d_cell = ws.cell(row=2, column=col_idx)
        d_cell.font = data_font
        if col_idx in (1, 2, 7, 14):
            d_cell.alignment = center_align
        elif col_idx in (6, 8, 9, 10):
            d_cell.alignment = right_align
        else:
            d_cell.alignment = left_align

    ws.column_dimensions['A'].width = 16
    for col_idx in range(2, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        val = str(sample_row[col_idx - 1])
        h_val = str(headers[col_idx - 1])
        width = max(len(val), len(h_val)) + 4
        ws.column_dimensions[col_letter].width = min(max(width, 12), 40)

    # Sheet 2: Instructions
    ws_inst = wb.create_sheet(title='Instructions')
    inst_headers = ['Colonne / Column', 'Requis / Required', 'Description', 'Exemple / Example']
    ws_inst.append(inst_headers)

    ws_inst.row_dimensions[1].height = 28
    inst_header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
    for col_idx in range(1, len(inst_headers) + 1):
        cell = ws_inst.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = inst_header_fill
        cell.alignment = header_align

    instructions_data = [
        (
            'Photo / Image',
            'Non / No',
            'Insérez une image directement dans la cellule (menu Insertion > Image) OU collez une URL d\'image (https://...) / Insert an image directly in the cell or paste an image URL',
            '[Image insérée ou https://...]'
        ),
        (
            'item_code',
            'Oui / Yes',
            'Code unique de l\'article / Unique item code (Obligatoire)',
            'ITEM-001'
        ),
        (
            'name',
            'Oui / Yes',
            'Nom de l\'article / Item name (Obligatoire)',
            'Ordinateur portable'
        ),
        (
            'category',
            'Non / No',
            'Nom de la catégorie (créée automatiquement si inexistante) / Category name',
            'Informatique'
        ),
        (
            'description',
            'Non / No',
            'Description de l\'article / Item description',
            'PC portable 15 pouces 16Go RAM'
        ),
        (
            'quantity',
            'Non / No',
            'Quantité initiale en stock / Initial stock quantity',
            '50'
        ),
        (
            'unit',
            'Non / No',
            'Unité: pcs, kg, ltr, box, set',
            'pcs'
        ),
        (
            'cost_price',
            'Non / No',
            'Prix de revient unitaire (pour valorisation du stock) / Cost price',
            '250000'
        ),
        (
            'selling_price',
            'Non / No',
            'Prix de vente unitaire (marketplace) / Selling price',
            '320000'
        ),
        (
            'reorder_level',
            'Non / No',
            'Seuil d\'alerte de stock bas / Reorder level',
            '10'
        ),
        (
            'supplier_name',
            'Non / No',
            'Nom du fournisseur / Supplier name',
            'Tech Distrib SARL'
        ),
        (
            'supplier_contact',
            'Non / No',
            'Contact fournisseur / Supplier contact',
            'contact@techdistrib.com'
        ),
        (
            'location',
            'Non / No',
            'Emplacement dans l\'entrepôt / Storage location',
            'Rayon B, Étagère 3'
        ),
        (
            'is_marketplace_visible',
            'Non / No',
            'Afficher sur la marketplace (true/false, yes/no, 1/0)',
            'true'
        ),
    ]

    for row_num, inst in enumerate(instructions_data, start=2):
        ws_inst.append(list(inst))
        ws_inst.row_dimensions[row_num].height = 24
        for col_idx in range(1, len(inst) + 1):
            cell = ws_inst.cell(row=row_num, column=col_idx)
            cell.font = data_font
            if col_idx == 2:
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    ws_inst.column_dimensions['A'].width = 24
    ws_inst.column_dimensions['B'].width = 18
    ws_inst.column_dimensions['C'].width = 65
    ws_inst.column_dimensions['D'].width = 30

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
