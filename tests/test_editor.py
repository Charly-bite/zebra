import unittest
import json
import os
from editor_app import app, TEMPLATES_DIR, EXCEL_FILE, read_equipment_data, generate_asset_zpl, build_zpl

class TestEditorApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_get_templates(self):
        response = self.app.get('/api/templates')
        data = json.loads(response.data)
        self.assertTrue(data['success'])

    def test_zpl_preview(self):
        payload = {
            "elements": [{"type": "text", "text": "Hello", "x": 10, "y": 10}],
            "canvasWidth": 500,
            "canvasHeight": 500
        }
        response = self.app.post('/api/zpl_preview', json=payload)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn("^FDHello^FS", data['zpl'])

if __name__ == '__main__':
    unittest.main()
