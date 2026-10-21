"""
Cleaning pipeline for the Emerald Home & Living sales data.
Run from the repo root:  python clean.py
Reads  data/raw/*.csv
Writes data/clean/Orders_cleaned.csv, customers_cleaned.csv, products.csv
"""
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
CLEAN = Path("data/clean")
CLEAN.mkdir(parents=True, exist_ok=True)

# ---------------- ORDERS ----------------
df = pd.read_csv(RAW / "raw_orders.csv")
products = pd.read_csv(RAW / "products.csv")

# 1. Dates: three formats in the same column
a = pd.to_datetime(df["order_date"], format="%Y-%m-%d", errors="coerce")
b = pd.to_datetime(df["order_date"], format="%d/%m/%Y", errors="coerce")
c = pd.to_datetime(df["order_date"], format="%d-%b-%y", errors="coerce")
d = pd.to_datetime(df["order_date"], format="%m/%d/%Y", errors="coerce")
df["order_date"] = a.fillna(b).fillna(c).fillna(d)
print("unparsed dates:", df["order_date"].isna().sum())

# 2. Sales amount stored as text with euro signs and commas
df["sales_amount"] = (
    df["sales_amount"].str.replace(",", "").str.replace("€", "")
).astype(float)

# 3. Duplicate order lines
df = df.drop_duplicates().copy()

# 4. Missing values
df["customer_id"] = df["customer_id"].fillna("unknown")
df["payment_method"] = df["payment_method"].fillna("unknown")
calculated_discount = (1 - df["sales_amount"] / (df["quantity"] * df["unit_price"])) * 100
df["discount_pct"] = df["discount_pct"].fillna(calculated_discount)

# 5. Standardise text labels
df["channel"] = df["channel"].str.lower().str.replace("in-store", "store").str.strip()
df["payment_method"] = df["payment_method"].str.lower().str.strip()

# 6. Quantity: negatives and values off by a factor of 100
df["quantity"] = df["quantity"].abs()
big = df["quantity"] > 50
df.loc[big, "quantity"] = df.loc[big, "quantity"] / 100

# 7. Zero unit price: use the product list price
list_price = df["product_id"].map(products.set_index("product_id")["unit_price"])
zero = df["unit_price"] == 0
df.loc[zero, "unit_price"] = list_price[zero]

# 8. Unit price that does not match sales amount: back-calculate it
expected = df["unit_price"] * df["quantity"] * (1 - df["discount_pct"] / 100)
bad = (expected - df["sales_amount"]).abs() > 0.05
df.loc[bad, "unit_price"] = (
    df.loc[bad, "sales_amount"]
    / (df.loc[bad, "quantity"] * (1 - df.loc[bad, "discount_pct"] / 100))
).round(2)

# 9. Duplicate line_id, future dates, discount rounding
df = df.drop_duplicates(subset="line_id").copy()
future = df["order_date"] > "2026-09-30"
df.loc[future, "order_date"] = pd.NaT
df = df.sort_values("order_id")
df["order_date"] = df["order_date"].ffill()
df["discount_pct"] = df["discount_pct"].round()

print("orders:", len(df), "| unique line_id:", df["line_id"].is_unique,
      "| orders:", df["order_id"].nunique())
print("date range:", df["order_date"].min(), "to", df["order_date"].max())

df.to_csv(CLEAN / "Orders_cleaned.csv", index=False)

# ---------------- CUSTOMERS ----------------
cstmr = pd.read_csv(RAW / "customers.csv")
cstmr["county"] = (
    cstmr["county"].str.strip()
    .str.replace(r"^[Cc]o\.?\s+", "", regex=True)
    .str.title()
)
lookup = (
    cstmr.dropna(subset=["region"])
    .drop_duplicates("county")
    .set_index("county")["region"]
)
cstmr["region"] = cstmr["region"].fillna(cstmr["county"].map(lookup))

print("customers:", len(cstmr), "| missing values:", cstmr.isna().sum().sum())
cstmr.to_csv(CLEAN / "customers_cleaned.csv", index=False)

# ---------------- PRODUCTS ----------------
products.to_csv(CLEAN / "products.csv", index=False)
print("done")
