from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from accounts.test_factories import create_test_company
from accounts.models import User
from inventory.models import StockCategory, Stock, StockTransaction
from inventory.services import adjust_stock, InsufficientStockError, marketplace_visible_stocks


class InventoryModelAndServiceTests(TestCase):
    def setUp(self):
        self.company = create_test_company(name="LogiCorp", domain="logicorp")
        self.user = User.objects.create_user(
            email="stockmgr@logicorp.io",
            password="password123",
            company=self.company,
            role="stock_manager"
        )
        self.category = StockCategory.objects.create(
            company=self.company,
            name="Hardware",
            description="Computer hardware components"
        )
        from suppliers.models import Supplier
        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Global Tech Supplies"
        )
        self.stock = Stock.objects.create(
            company=self.company,
            item_code="HW-001",
            name="Wireless Mouse",
            category=self.category,
            quantity=50,
            unit="pcs",
            cost_price=Decimal("15.00"),
            selling_price=Decimal("25.00"),
            reorder_level=10,
            supplier=self.supplier,
            is_marketplace_visible=True,
            created_by=self.user,
        )

    def test_stock_category_creation(self):
        self.assertEqual(str(self.category), "Hardware (LogiCorp)")
        with self.assertRaises(IntegrityError):
            StockCategory.objects.create(
                company=self.company,
                name="Hardware"  # Duplicate in same company
            )

    def test_stock_calculations(self):
        self.assertEqual(self.stock.total_value, Decimal("750.00"))
        self.assertEqual(self.stock.total_selling_value, Decimal("1250.00"))
        self.assertFalse(self.stock.needs_reorder)

        # Drop quantity below reorder level
        self.stock.quantity = 8
        self.stock.save()
        self.assertTrue(self.stock.needs_reorder)

    def test_adjust_stock_positive(self):
        updated_stock = adjust_stock(self.stock.pk, delta=20)
        self.assertEqual(updated_stock.quantity, 70)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 70)

    def test_adjust_stock_negative(self):
        updated_stock = adjust_stock(self.stock.pk, delta=-30)
        self.assertEqual(updated_stock.quantity, 20)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 20)

    def test_adjust_stock_insufficient_error(self):
        with self.assertRaises(InsufficientStockError):
            adjust_stock(self.stock.pk, delta=-100)

        # Quantity should remain intact
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 50)

    def test_marketplace_visible_stocks(self):
        # Initial stock should be visible
        visible = marketplace_visible_stocks(company=self.company)
        self.assertIn(self.stock, visible)

        # Stock with quantity 0 should not be visible
        self.stock.quantity = 0
        self.stock.save()
        self.assertNotIn(self.stock, marketplace_visible_stocks(company=self.company))

        # Restocked but is_marketplace_visible=False
        self.stock.quantity = 10
        self.stock.is_marketplace_visible = False
        self.stock.save()
        self.assertNotIn(self.stock, marketplace_visible_stocks(company=self.company))

    def test_stock_transaction_creation(self):
        txn = StockTransaction.objects.create(
            company=self.company,
            stock=self.stock,
            transaction_type="in",
            quantity=25,
            remarks="Initial shipment received",
            user=self.user,
        )
        self.assertEqual(txn.stock, self.stock)
        self.assertEqual(txn.quantity, 25)
        self.assertIn("HW-001 - in - 25", str(txn))

    def test_tenant_stock_isolation(self):
        from suppliers.models import Supplier
        other_company = create_test_company(name="Other Co", domain="other-co")
        other_supplier = Supplier.objects.create(
            company=other_company,
            name="Other Supplier"
        )
        other_stock = Stock.objects.create(
            company=other_company,
            item_code="HW-001",  # Same code allowed in different company
            name="Other Item",
            quantity=10,
            cost_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            reorder_level=2,
            supplier=other_supplier,
        )
        company_stocks = Stock.objects.filter(company=self.company)
        self.assertIn(self.stock, company_stocks)
        self.assertNotIn(other_stock, company_stocks)


class InventoryExcelPhotoTests(TestCase):
    def setUp(self):
        import io
        from PIL import Image as PILImage
        from django.core.files.base import ContentFile
        from suppliers.models import Supplier

        self.company = create_test_company(name="PhotoCorp", domain="photocorp")
        self.user = User.objects.create_user(
            email="manager@photocorp.io",
            password="password123",
            company=self.company,
            role="admin"
        )
        self.client.force_login(self.user)

        self.supplier_vision = Supplier.objects.create(
            company=self.company,
            name="Vision Supplies"
        )
        self.supplier_cable = Supplier.objects.create(
            company=self.company,
            name="CableCo"
        )

        # Create a sample test image
        img = PILImage.new('RGB', (120, 100), color=(30, 144, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        self.test_img_bytes = buf.getvalue()

        # Create a stock item with image
        self.stock_with_img = Stock.objects.create(
            company=self.company,
            item_code="CAM-001",
            name="HD Webcam",
            quantity=20,
            unit="pcs",
            cost_price=Decimal("35.00"),
            selling_price=Decimal("59.99"),
            reorder_level=5,
            supplier=self.supplier_vision,
            is_marketplace_visible=True,
            created_by=self.user,
        )
        self.stock_with_img.image.save('cam001.png', ContentFile(self.test_img_bytes), save=True)

        # Create a stock item without image
        self.stock_no_img = Stock.objects.create(
            company=self.company,
            item_code="CBL-002",
            name="USB-C Cable",
            quantity=100,
            unit="pcs",
            cost_price=Decimal("2.50"),
            selling_price=Decimal("8.00"),
            reorder_level=15,
            supplier=self.supplier_cable,
            is_marketplace_visible=True,
            created_by=self.user,
        )

    def test_generate_stock_export_excel_with_photo(self):
        import io
        import openpyxl
        from inventory.excel_services import generate_stock_export_excel

        stocks = Stock.objects.filter(company=self.company).order_by('item_code')
        excel_bytes = generate_stock_export_excel(stocks)
        self.assertGreater(len(excel_bytes), 0)

        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
        ws = wb.active
        self.assertEqual(ws.title, 'Stock Data')

        # Check headers
        self.assertEqual(ws.cell(row=1, column=1).value, 'Photo')
        self.assertEqual(ws.cell(row=1, column=2).value, 'Item Code')
        self.assertEqual(ws.cell(row=1, column=3).value, 'Name')

        # Check embedded image in ws._images
        self.assertGreaterEqual(len(ws._images), 1)
        exported_img = ws._images[0]
        # Row 0 in 0-indexed anchor is row 1 in Excel; row 1 in 0-indexed is row 2
        self.assertEqual(exported_img.anchor._from.row, 1)  # Row 2 in Excel
        self.assertEqual(exported_img.anchor._from.col, 0)  # Col A in Excel
        self.assertGreater(len(exported_img._data()), 0)

    def test_generate_stock_template_excel(self):
        import io
        import openpyxl
        from inventory.excel_services import generate_stock_template_excel

        template_bytes = generate_stock_template_excel()
        self.assertGreater(len(template_bytes), 0)

        wb = openpyxl.load_workbook(io.BytesIO(template_bytes), data_only=True)
        self.assertIn('Template', wb.sheetnames)
        self.assertIn('Instructions', wb.sheetnames)

        ws_template = wb['Template']
        self.assertEqual(ws_template.cell(row=1, column=1).value, 'Photo')
        self.assertEqual(ws_template.cell(row=1, column=2).value, 'item_code')

        ws_inst = wb['Instructions']
        found_photo_instruction = False
        for r in range(2, ws_inst.max_row + 1):
            if 'photo' in str(ws_inst.cell(row=r, column=1).value).lower():
                found_photo_instruction = True
                break
        self.assertTrue(found_photo_instruction)

    def test_stock_import_with_embedded_photo(self):
        import io
        from PIL import Image as PILImage
        import openpyxl
        from openpyxl.drawing.image import Image as OpenpyxlImage
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create workbook with image
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Photo', 'item_code', 'name', 'quantity', 'cost_price', 'selling_price'])
        ws.append(['', 'MIC-001', 'USB Microphone', 30, 25.00, 49.99])

        # Create dummy image to embed
        mic_img = PILImage.new('RGB', (80, 80), color=(255, 105, 180))
        img_buf = io.BytesIO()
        mic_img.save(img_buf, format='PNG')
        img_buf.seek(0)

        ox_img = OpenpyxlImage(img_buf)
        ws.add_image(ox_img, 'A2')

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)

        uploaded = SimpleUploadedFile(
            'import_with_photo.xlsx',
            excel_buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        url = reverse('inventory:stock_import')
        response = self.client.post(url, {'excel_file': uploaded}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Check that stock was created and image saved
        imported_stock = Stock.objects.filter(company=self.company, item_code='MIC-001').first()
        self.assertIsNotNone(imported_stock)
        self.assertEqual(imported_stock.name, 'USB Microphone')
        self.assertEqual(imported_stock.quantity, 30)
        self.assertTrue(bool(imported_stock.image))
        self.assertGreater(imported_stock.image.size, 0)

    def test_stock_import_with_french_headers(self):
        import io
        import openpyxl
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Code Article', 'Désignation', 'Quantité', 'Prix d\'achat', 'Prix de vente'])
        ws.append(['MON-FR-01', 'Ecran 4K 27 pouces', 12, 180000, 240000])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)

        uploaded = SimpleUploadedFile(
            'import_fr.xlsx',
            excel_buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        url = reverse('inventory:stock_import')
        response = self.client.post(url, {'excel_file': uploaded}, follow=True)
        self.assertEqual(response.status_code, 200)

        stock = Stock.objects.filter(company=self.company, item_code='MON-FR-01').first()
        self.assertIsNotNone(stock)
        self.assertEqual(stock.name, 'Ecran 4K 27 pouces')
        self.assertEqual(stock.quantity, 12)
        self.assertEqual(stock.cost_price, Decimal('180000.00'))
        self.assertEqual(stock.selling_price, Decimal('240000.00'))

    def test_export_then_reimport_with_photo(self):
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1. Export
        export_resp = self.client.get(reverse('inventory:stock_export'))
        self.assertEqual(export_resp.status_code, 200)

        # 2. Re-import
        uploaded = SimpleUploadedFile(
            'reimport.xlsx',
            export_resp.content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        import_resp = self.client.post(
            reverse('inventory:stock_import'),
            {'excel_file': uploaded},
            follow=True
        )
        self.assertEqual(import_resp.status_code, 200)

        # Check CAM-001 still has image
        stock = Stock.objects.get(company=self.company, item_code='CAM-001')
        self.assertTrue(bool(stock.image))
        self.assertGreater(stock.image.size, 0)

    def test_stock_export_endpoint(self):
        from django.urls import reverse

        url = reverse('inventory:stock_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('stock_export.xlsx', response['Content-Disposition'])
        self.assertGreater(len(response.content), 0)

    def test_stock_download_template_endpoint(self):
        from django.urls import reverse

        url = reverse('inventory:stock_download_template')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('stock_import_template.xlsx', response['Content-Disposition'])
        self.assertGreater(len(response.content), 0)

