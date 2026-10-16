"""ATLAS products in parts: the capability catalogue, receipts, geometry, and the product
functions grouped by what they read. ``atlas.products`` re-exports every name here and
dispatches calls in ``invoke_product``. This code reads that module at call time
(``products.<name>``), so a value set or patched there reaches it.
"""
