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

    def test_stock_resolver(self):
        # Create a mock All File dataframe with the new column headers
        all_data = pd.DataFrame({
            'sellerSKU': ['A', 'B', 'C', '10023.0'],
            'MyStock-1 quantity': [100, 50, 15, '20'],
            'MyStock-1 reservedQuantity': [10, 5, 2, '0']
        })
        resolver = StockResolver(all_data)
        
        # Test base lookup
        self.assertEqual(resolver.get_tc_stock('A'), 100)
        self.assertEqual(resolver.get_tc_stock('B'), 50)
        self.assertEqual(resolver.get_tc_stock('10023'), 20)
        self.assertEqual(resolver.get_tc_stock('D'), 0) # Missing SKU
        
        # Test '+' bundle (e.g. A+B)
        self.assertEqual(resolver.get_tc_stock('A+B'), 50) # min(100, 50)
        self.assertEqual(resolver.get_tc_stock('A+B+C'), 15) # min(100, 50, 15)
        
        # Test 'X' bundle (e.g. AX2, BX3)
        self.assertEqual(resolver.get_tc_stock('AX2'), 50) # 100 // 2
        self.assertEqual(resolver.get_tc_stock('BX3'), 16) # 50 // 3 = 16
        
        # Test combination bundle
        self.assertEqual(resolver.get_tc_stock('AX2+BX2'), 25)

    def test_evaluate_sku_logic(self):
        # 1. Status Check = False -> Stock = 0 -> Change to inactive
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Inactive', mp_stock=0, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertFalse(status_chk)
        self.assertEqual(action, "Change to inactive")

        # 2. Status Check = False -> Stock = More than 1 -> Change to Inactive
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Inactive', mp_stock=5, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertFalse(status_chk)
        self.assertEqual(action, "Change to Inactive")

        # 3. Status Check = True -> Stock Check = false -> TC Status = Active Reserved = 0 and Max 0 = No -> Make Impact
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=10, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Make Impact")

        # 4. Status Check = True -> Stock Check = false -> TC Status = Active Reserved = not equal to 0 -> Reserved stock
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=10, tc_stock=5, reserved_stock=2, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Reserved stock")

        # 5. Status Check = True -> Stock Check = false -> TC Status = Inactive -> Stock not pushed due to Inactive Status
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=10, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertFalse(stock_chk)
        self.assertEqual(action, "Stock not pushed due to Inactive Status")

        # 6. Status Check = True -> Stock Check = True -> TC Stock = 0 -> Change to Inactive (if not inactive)
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=0, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "Change to Inactive")

        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=0, tc_stock=0, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "All Good")

        # 7. Status Check = True -> Stock Check = True -> TC Stock > 0 -> Change to Active (if not active)
        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Inactive', tc_status='Inactive', mp_stock=5, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "Change to Active")

        status_chk, stock_chk, action = evaluate_sku_logic(
            mp_status='Active', tc_status='Active', mp_stock=5, tc_stock=5, reserved_stock=0, max_0='No'
        )
        self.assertTrue(status_chk)
        self.assertTrue(stock_chk)
        self.assertEqual(action, "All Good")

if __name__ == '__main__':
    unittest.main()
