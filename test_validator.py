import unittest
import pandas as pd
import numpy as np
from validator import clean_sku, StockResolver, evaluate_sku_logic, validate_lazada, validate_shopee, validate_tiktok

class TestStockValidator(unittest.TestCase):
    def test_clean_sku(self):
        self.assertEqual(clean_sku("  A  "), "A")
        self.assertEqual(clean_sku("12345.0"), "12345")
        self.assertEqual(clean_sku("12345"), "12345")
        self.assertEqual(clean_sku(np.nan), "")
        self.assertEqual(clean_sku(None), "")

    def test_stock_resolver_no_buffer(self):
        # Create a mock All File dataframe
        all_data = pd.DataFrame({
            'sellerSKU': ['A', 'B', 'C', '10023.0'],
            'MyStock-1 quantity': [100, 50, 15, '20'],
            'MyStock-1 reservedQuantity': [10, 5, 2, '0']
        })
        resolver = StockResolver(all_data)
        
        # Test base lookup
        self.assertEqual(resolver.get_tc_stock('A'), 100)
        self.assertEqual(resolver.get_tc_stock('B'), 50)
        
        # Test '+' bundle (e.g. A+B)
        self.assertEqual(resolver.get_tc_stock('A+B'), 50) # min(100, 50)
        
        # Test 'X' bundle (e.g. AX2)
        self.assertEqual(resolver.get_tc_stock('AX2'), 50) # 100 // 2

    def test_stock_resolver_inventory_buffer(self):
        all_data = pd.DataFrame({
            'sellerSKU': ['A', 'B'],
            'MyStock-1 quantity': [10, 50],
            'MyStock-1 reservedQuantity': [0, 0]
        })
        # Inventory Buffer = 2
        resolver = StockResolver(all_data, buffer_type="Inventory Buffer", buffer_val=2)
        
        # 10 - 2 = 8
        self.assertEqual(resolver.get_tc_stock('A'), 8)
        # 50 - 2 = 48
        self.assertEqual(resolver.get_tc_stock('B'), 48)
        
        # Combo A+B stock should be min(raw_A, raw_B) - buffer
        # raw_A = 10, raw_B = 50 -> min(10, 50) = 10 -> 10 - 2 = 8
        self.assertEqual(resolver.get_tc_stock('A+B'), 8)
        
        # AX2: raw_A = 10 -> 10 // 2 = 5 -> 5 - 2 = 3
        self.assertEqual(resolver.get_tc_stock('AX2'), 3)

    def test_stock_resolver_percentage_buffer(self):
        all_data = pd.DataFrame({
            'sellerSKU': ['A'],
            'MyStock-1 quantity': [10],
            'MyStock-1 reservedQuantity': [0]
        })
        # Percentage Buffer = 5% (reduction)
        # 10 * (1 - 0.05) = 9.5 -> 9
        resolver = StockResolver(all_data, buffer_type="Percentage Buffer", buffer_val=5.0)
        self.assertEqual(resolver.get_tc_stock('A'), 9)

    def test_evaluate_sku_logic(self):
        # Rule 1: Status Check = False -> Stock=0 -> Change to inactive
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Inactive', mp_stock=0, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertFalse(status_chk)
        self.assertEqual(action, "Change to inactive")

        # Rule 2: Status Check = False -> Stock=More than 1 -> Change to Active
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Inactive', mp_stock=5, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertFalse(status_chk)
        self.assertEqual(action, "Change to Active")

        # Rule 3: Status Check = True -> Stock Check = false -> TC Status = Active Reserved = 0 and Max 0 = No -> Make Impact
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=10, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Make Impact")

        # Rule 4: Status Check = True -> Stock Check = false -> TC Status = Active Reserved = not equal to 0 -> Reserved stock
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=10, tc_stock=5, reserved_stock=2, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Reserved stock")

        # New Rule: Status Check = True -> Stock Check = false -> TC Status = Inactive -> TC Stock more than 0 stock -> Change to Active Status
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=10, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Change to Active Status")

        # Rule 5: Status Check = True -> Stock Check = false -> TC Status = Inactive -> TC Stock = 0 -> Stock not pushed due to Inactive Status
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=10, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Stock not pushed due to Inactive Status")

        # Rule 6: Status Check = True -> Stock Check = True -> TC Stock = 0 both TC & MP Status should be Inactive. If not -> Change to Inactive else All Good.
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=0, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "Change to Inactive")

        # Rule 7: Status Check = True -> Stock Check = True -> TC Stock more than 0 both TC & MP Status should be Active. If not -> Change to Active else All Good.
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=5, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "Change to Active")

    def test_validate_lazada_column_renaming(self):
        # Mock Lazada and Reference dataframes
        lazada_df = pd.DataFrame({
            'SellerSKU': ['A'],
            'Quantity': [10],
            'status': ['Active']
        })
        tc_inv = pd.DataFrame({
            'Custom SKU': ['A'],
            'Item status': ['Active'],
            'Max Quantity': [10]
        })
        all_data = pd.DataFrame({
            'sellerSKU': ['A'],
            'MyStock-1 quantity': [10],
            'MyStock-1 reservedQuantity': [0]
        })
        
        res = validate_lazada(lazada_df, tc_inv, all_data)
        
        # Verify column renamed from 'Buffer (TC - MP)' to 'QTY Difference'
        self.assertIn('QTY Difference', res.columns)
        self.assertNotIn('Buffer (TC - MP)', res.columns)

    def test_validate_lazada_multiple_headers(self):
        # Mock Lazada dataframes with different headers from the list
        lazada_df_1 = pd.DataFrame({
            'SellerSKU': ['A'],
            'DKSH SINGAPORE': [15],
            'status': ['Active']
        })
        lazada_df_2 = pd.DataFrame({
            'SellerSKU': ['A'],
            'SMITH & NEPHEW': [22],
            'status': ['Active']
        })
        tc_inv = pd.DataFrame({
            'Custom SKU': ['A'],
            'Item status': ['Active'],
            'Max Quantity': [10]
        })
        all_data = pd.DataFrame({
            'sellerSKU': ['A'],
            'MyStock-1 quantity': [10],
            'MyStock-1 reservedQuantity': [0]
        })
        
        res_1 = validate_lazada(lazada_df_1, tc_inv, all_data)
        res_2 = validate_lazada(lazada_df_2, tc_inv, all_data)
        
        self.assertEqual(res_1.iloc[0]['MP Stock (Lazada)'], 15)
        self.assertEqual(res_2.iloc[0]['MP Stock (Lazada)'], 22)

if __name__ == '__main__':
    unittest.main()
