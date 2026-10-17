"""
Step 0 — generate synthetic Indian e-commerce data (seeded, reproducible).

Produces 4 CSVs in data/raw/:
    customers.csv   (~8,000 rows)
    products.csv    (~500 rows)
    orders.csv      (~50,000 rows)
    order_items.csv (~85,000 rows, 1-3 line items per order)

Everything is fake: names, emails, phones and addresses are generated.
random.seed(42) makes every run produce the exact same dataset.

A small amount of realistic "mess" is injected on purpose so the
transform step has something real to clean:
  * leading/trailing spaces in some names
  * mixed casing in status / payment_method ("delivered", "DELIVERED", "upi")
  * a few blank emails and blank discounts
  * a handful of exact-duplicate order_items rows

Run:  python generate_data.py
"""
import csv
import os
import random
from datetime import date, timedelta

SEED = 42
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

N_CUSTOMERS = 8000
N_PRODUCTS = 500
N_ORDERS = 50000

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 6, 30)

# ---------------------------------------------------------------- names ----
FIRST_NAMES = [
    "Aarav", "Aditya", "Aisha", "Akash", "Ananya", "Anil", "Anjali", "Arjun",
    "Asha", "Avinash", "Deepak", "Deepika", "Divya", "Farhan", "Gaurav",
    "Harish", "Ishaan", "Isha", "Kabir", "Karan", "Kavya", "Kiran", "Krishna",
    "Lakshmi", "Manoj", "Meera", "Mohammed", "Neha", "Nikhil", "Nisha",
    "Pooja", "Pranav", "Priya", "Rahul", "Rajesh", "Ravi", "Rekha", "Rohan",
    "Rohit", "Riya", "Sachin", "Sahil", "Sana", "Sandeep", "Sanjay", "Shreya",
    "Shubham", "Sneha", "Suresh", "Swati", "Varun", "Vikram", "Vikas",
    "Vishal", "Yash", "Zoya", "Aditi", "Kunal", "Pallavi", "Ritu",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Mehta", "Iyer", "Reddy", "Nair", "Menon",
    "Patel", "Shah", "Khan", "Singh", "Kaur", "Yadav", "Mishra", "Tiwari",
    "Dubey", "Chopra", "Malhotra", "Kapoor", "Bose", "Chatterjee", "Das",
    "Ghosh", "Pillai", "Rao", "Kulkarni", "Deshmukh", "Joshi", "Pawar",
    "Agarwal", "Bansal", "Jain", "Kohli", "Arora", "Bhatt", "Trivedi",
    "Pandey", "Chauhan", "Rathore",
]

# ------------------------------------------------------- cities & states ----
# (city, state, weight) — weights make metros realistically larger.
CITIES = [
    ("Mumbai", "Maharashtra", 14), ("Delhi", "Delhi", 13),
    ("Bengaluru", "Karnataka", 11), ("Hyderabad", "Telangana", 9),
    ("Chennai", "Tamil Nadu", 8), ("Kolkata", "West Bengal", 7),
    ("Pune", "Maharashtra", 7), ("Ahmedabad", "Gujarat", 6),
    ("Jaipur", "Rajasthan", 5), ("Lucknow", "Uttar Pradesh", 5),
    ("Kochi", "Kerala", 4), ("Indore", "Madhya Pradesh", 4),
    ("Surat", "Gujarat", 3), ("Nagpur", "Maharashtra", 2),
    ("Chandigarh", "Chandigarh", 2),
]

# ------------------------------------------------------------- products ----
# (category, item, brand, min_price_inr, max_price_inr)
CATALOG = {
    "Electronics": [
        ("Bluetooth Earbuds", ["boAt", "Noise", "Mivi", "realme"], 999, 4999),
        ("Smartwatch", ["Noise", "boAt", "Fire-Boltt", "Amazfit"], 1499, 12999),
        ("Laptop", ["HP", "Dell", "Lenovo", "Asus"], 32990, 89990),
        ("Mixer Grinder", ["Prestige", "Bajaj", "Philips", "Sujata"], 2499, 8999),
        ("LED TV 43 inch", ["Mi", "Samsung", "LG", "OnePlus"], 21999, 45999),
        ("Ceiling Fan", ["Crompton", "Havells", "Orient", "Usha"], 1499, 4999),
        ("Power Bank 20000mAh", ["Mi", "URBN", "Ambrane", "boAt"], 999, 2999),
        ("Wireless Mouse", ["Logitech", "HP", "Dell", "Zebronics"], 499, 2499),
    ],
    "Fashion": [
        ("Men's Kurta", ["Manyavar", "FabIndia", "Peter England"], 799, 3999),
        ("Saree", ["FabIndia", "Sabyasachi", "Nalli", "Meena Bazaar"], 999, 8999),
        ("Running Shoes", ["Puma", "Adidas", "Nike", "HRX"], 1499, 9999),
        ("Denim Jeans", ["Levi's", "Roadster", "Wrangler", "HRX"], 999, 3999),
        ("Handbag", ["Lavie", "Caprese", "H&M", "Zouk"], 899, 4999),
        ("Analog Watch", ["Titan", "Fastrack", "Casio", "Timex"], 1499, 9999),
        ("Cotton T-Shirt", ["Roadster", "HRX", "Bewakoof", "Veirdo"], 299, 1499),
        ("Sunglasses", ["Fastrack", "Vincent Chase", "John Jacobs"], 799, 3499),
    ],
    "Home & Kitchen": [
        ("Pressure Cooker 5L", ["Prestige", "Hawkins", "Pigeon"], 1299, 3999),
        ("Cotton Bedsheet Set", ["Bombay Dyeing", "Wakefit", "Story@Home"], 499, 2499),
        ("Dinner Set 27pc", ["Cello", "La Opala", "Borosil"], 999, 4999),
        ("Memory Foam Mattress", ["Wakefit", "Sleepwell", "Duroflex"], 4999, 24999),
        ("Storage Box Set", ["Cello", "Milton", "Nayasa"], 399, 1999),
        ("LED Bulb Pack of 6", ["Philips", "Havells", "Wipro"], 499, 1499),
        ("Non-stick Cookware Set", ["Prestige", "Hawkins", "Pigeon"], 1499, 5999),
    ],
    "Beauty": [
        ("Face Wash 150ml", ["Himalaya", "Mamaearth", "Nivea", "Pond's"], 99, 499),
        ("Herbal Shampoo", ["Mamaearth", "WOW", "Biotique", "Khadi"], 199, 699),
        ("Kajal Pencil", ["Lakme", "Maybelline", "Colorbar"], 149, 499),
        ("Moisturizer 200ml", ["Nivea", "Pond's", "Dot & Key", "Plum"], 199, 899),
        ("Vitamin C Serum", ["Mamaearth", "Dot & Key", "Plum", "Minimalist"], 399, 1299),
        ("Hair Oil 200ml", ["Parachute", "Dabur Amla", "Indulekha"], 99, 599),
    ],
    "Sports": [
        ("Cricket Bat", ["SG", "SS", "MRF", "Cosco"], 899, 6999),
        ("Football Size 5", ["Nivia", "Cosco", "Vector X"], 499, 2499),
        ("Yoga Mat 6mm", ["Boldfit", "Strauss", "Amazon Brand"], 399, 1499),
        ("Badminton Racket", ["Yonex", "Li-Ning", "Cosco"], 799, 3999),
        ("Dumbbell Set 10kg", ["Kore", "Boldfit", "Strauss"], 999, 3999),
    ],
    "Grocery": [
        ("Atta 5kg", ["Aashirvaad", "Fortune", "Pillsbury"], 199, 349),
        ("Basmati Rice 5kg", ["India Gate", "Daawat", "Fortune"], 399, 899),
        ("Toor Dal 1kg", ["Tata Sampann", "Aashirvaad", "Fortune"], 120, 220),
        ("Mustard Oil 1L", ["Fortune", "Dhara", "Emami"], 150, 280),
        ("Tea Powder 500g", ["Tata Tea", "Brooke Bond", "Wagh Bakri"], 140, 320),
        ("Sugar 1kg", ["Madhur", "Parry's", "Trust"], 45, 75),
    ],
}

PAYMENT_METHODS = [
    ("UPI", 45), ("Cash on Delivery", 15), ("Credit Card", 15),
    ("Debit Card", 12), ("Netbanking", 8), ("Wallet", 5),
]
# Canonical short labels used in the CSVs (transform normalises variants).
PAYMENT_LABELS = {
    "UPI": "UPI", "Cash on Delivery": "COD", "Credit Card": "Credit Card",
    "Debit Card": "Debit Card", "Netbanking": "Netbanking", "Wallet": "Wallet",
}

STATUS_WEIGHTS = [("Delivered", 86), ("Cancelled", 8), ("Returned", 6)]
# Fashion gets returned more often (size/fit issues) — realistic touch.
FASHION_RETURN_BOOST = 0.06


def weighted_choice(weighted):
    total = sum(w for _, w in weighted)
    r = random.uniform(0, total)
    upto = 0
    for value, weight in weighted:
        upto += weight
        if r <= upto:
            return value
    return weighted[-1][0]


def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def messy(text, space_chance=0.02, case_variant_chance=0.05):
    """Inject realistic mess: stray spaces and odd casing."""
    if random.random() < space_chance:
        text = (" " if random.random() < 0.5 else "") + text + (
            " " if random.random() < 0.5 else "")
    if random.random() < case_variant_chance:
        variant = random.random()
        text = text.lower() if variant < 0.5 else text.upper()
    return text


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    # ---------------------------------------------------------- customers ----
    customers = []
    used_emails = set()
    city_pool = [(c, s) for c, s, _ in CITIES for _ in range(
        next(w for cc, ss, w in CITIES if cc == c))]
    for i in range(1, N_CUSTOMERS + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city, state = random.choice(city_pool)
        email = f"{first.lower()}.{last.lower()}{random.randint(1, 9999)}@example.in"
        while email in used_emails:  # keep emails unique
            email = f"{first.lower()}.{last.lower()}{random.randint(1, 99999)}@example.in"
        used_emails.add(email)
        if random.random() < 0.01:
            email = ""  # a few blank emails for the cleaner to handle
        signup = random_date(date(2023, 1, 1), date(2024, 6, 30))
        customers.append({
            "customer_id": f"C{i:05d}",
            "first_name": messy(first),
            "last_name": messy(last),
            "email": email,
            "phone": f"{random.randint(6, 9)}{random.randint(10**8, 10**9 - 1)}",
            "city": city,
            "state": state,
            "signup_date": signup.isoformat(),
        })

    # ----------------------------------------------------------- products ----
    products = []
    pid = 1
    per_category = N_PRODUCTS // len(CATALOG)
    for category, items in CATALOG.items():
        for _ in range(per_category):
            item, brands, lo, hi = random.choice(items)
            brand = random.choice(brands)
            price = round(random.uniform(lo, hi), 2)
            cost = round(price * random.uniform(0.55, 0.75), 2)
            products.append({
                "product_id": f"P{pid:04d}",
                "product_name": f"{brand} {item}",
                "category": category,
                "brand": brand,
                "price_inr": f"{price:.2f}",
                "cost_inr": f"{cost:.2f}",
            })
            pid += 1
    while pid <= N_PRODUCTS:  # top-up if division left a remainder
        item, brands, lo, hi = random.choice(CATALOG["Grocery"])
        brand = random.choice(brands)
        price = round(random.uniform(lo, hi), 2)
        products.append({
            "product_id": f"P{pid:04d}",
            "product_name": f"{brand} {item}",
            "category": "Grocery",
            "brand": brand,
            "price_inr": f"{price:.2f}",
            "cost_inr": f"{round(price * 0.65, 2):.2f}",
        })
        pid += 1

    # ------------------------------------------------------------- orders ----
    orders, order_items = [], []
    item_seq = 1
    for i in range(1, N_ORDERS + 1):
        cust = random.choice(customers)
        signup = date.fromisoformat(cust["signup_date"])
        order_date = random_date(max(signup, START_DATE), END_DATE)

        category_hint = random.choice(list(CATALOG.keys()))
        status = weighted_choice(STATUS_WEIGHTS)
        if status == "Delivered" and category_hint == "Fashion" \
                and random.random() < FASHION_RETURN_BOOST:
            status = "Returned"  # fashion return-rate boost

        payment = PAYMENT_LABELS[weighted_choice(PAYMENT_METHODS)]
        ship_city, ship_state = (cust["city"], cust["state"]) \
            if random.random() < 0.9 else random.choice(
                [(c, s) for c, s, _ in CITIES])
        orders.append({
            "order_id": f"O{i:06d}",
            "customer_id": cust["customer_id"],
            "order_date": order_date.isoformat(),
            "status": messy(status),
            "payment_method": messy(payment),
            "shipping_city": ship_city,
            "shipping_state": ship_state,
        })

        n_items = random.choices([1, 2, 3], weights=[50, 30, 20])[0]
        for _ in range(n_items):
            prod = random.choice(products)
            qty = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
            discount = 0.0 if random.random() < 0.45 else round(
                random.uniform(5, 30), 1)
            discount_str = "" if random.random() < 0.01 else f"{discount:.1f}"
            order_items.append({
                "order_item_id": f"OI{item_seq:07d}",
                "order_id": f"O{i:06d}",
                "product_id": prod["product_id"],
                "quantity": str(qty),
                "unit_price_inr": prod["price_inr"],
                "discount_pct": discount_str,
            })
            item_seq += 1

    # a few exact-duplicate line items (dedup is the transform's job)
    order_items += random.sample(order_items, 30)

    # -------------------------------------------------------------- write ----
    def write_csv(name, rows, fieldnames):
        path = os.path.join(RAW_DIR, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path} ({len(rows):,} rows)")

    write_csv("customers.csv", customers, list(customers[0].keys()))
    write_csv("products.csv", products, list(products[0].keys()))
    write_csv("orders.csv", orders, list(orders[0].keys()))
    write_csv("order_items.csv", order_items, list(order_items[0].keys()))
    print("done.")


if __name__ == "__main__":
    main()
