import sqlite3
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field

DATABASE_NAME = "toko.db"



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan handler untuk inisialisasi tabel dan seeding data otomatis
    agar mempermudah pengujian endpoint laporan di Swagger UI.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # 1.Tabel
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        email TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_produk TEXT NOT NULL,
        kategori TEXT NOT NULL,
        harga REAL NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        jumlah INTEGER NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """)
    
    # 2. Seeding Data Otomatis (Jika Database Masih Kosong)
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        # Tambah Customers
        cursor.executemany("INSERT INTO customers (nama, email) VALUES (?, ?)", [
            ("Tifa", "tifa@mail.com"),
            ("Fira", "fira@mail.com"),
            ("Khaliq", "khaliq@mail.com"),
            ("Fatir", "fatir@mail.com")
        ])
        
        # Tambah Products
        cursor.executemany("INSERT INTO products (nama_produk, kategori, harga) VALUES (?, ?, ?)", [
            ("Hp Iphone  17 pro max", "Elektronik", 25000000),
            ("Laptop asus THINKPAD", "Elektronik", 3000000),
            ("Baju batik", "Fashion", 250000),
            ("Sepatu ADIDAS samba", "Fashion", 600000),
            ("Kopi Susu", "FnB", 45000),
            ("mojito anggur", "FnB", 35000)
        ])
        
        # Tambah Orders (Transaksi)
        # Tifa belanja Laptop Asus x1 -> Total: 7.500.000 (VIP)
        # Fira belanja Sneakers x1 + Matcha x2 -> Total: 1.270.000 (Regular)
        # Khaliq belanja Mouse x2 -> Total: 300.000 (Basic)
        # Fatir belanja Kemeja x1 + Kopi x1 -> Total: 295.000 (Basic)
        cursor.executemany("INSERT INTO orders (customer_id, product_id, jumlah) VALUES (?, ?, ?)", [
            (1, 1, 1),
            (2, 4, 1),
            (2, 6, 2),
            (3, 2, 2),
            (4, 3, 1),
            (4, 5, 1)
        ])
        conn.commit()
        print("[DB] Berhasil menginisialisasi database dan seeding data simulasi!")
        
    conn.close()
    yield


app = FastAPI(
    title="API Toko Online",
    description="Implementasi CRUD Dasar dan Query Analisis Kompleks dengan FastAPI + SQLite (Raw SQL)",
    version="1.0.0",
    lifespan=lifespan
)


# Dependency untuk koneksi DB per request
def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Memungkinkan akses kolom via key/nama kolom
    try:
        yield conn
    finally:
        conn.close()


# Product Schema
class ProductBase(BaseModel):
    nama_produk: str = Field(..., min_length=2, examples=["Hp Iphone  17 pro max"])
    kategori: str = Field(..., examples=["Elektronik"])
    harga: float = Field(..., gt=0, examples=[7500000.0])

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int

# Report Schema
class CustomerTotalReport(BaseModel):
    nama: str
    total_belanja: float

class CustomerAboveAverageReport(BaseModel):
    nama: str
    total_belanja: float

class TopProductReport(BaseModel):
    kategori: str
    nama_produk: str
    total_terjual: int

class CustomerLevelReport(BaseModel):
    nama: str
    total_belanja: float
    level_customer: str


# SOAL 1: CRUD PRODUCTS ENDPOINTS

@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, tags=["Products"])
def create_product(product: ProductCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO products (nama_produk, kategori, harga) VALUES (?, ?, ?)",
        (product.nama_produk, product.kategori, product.harga)
    )
    db.commit()
    product_id = cursor.lastrowid
    return {**product.model_dump(), "id": product_id}


@app.get("/products", response_model=List[ProductResponse], tags=["Products"])
def read_products(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def read_product_by_id(product_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Produk dengan ID {product_id} tidak ditemukan"
        )
    return dict(row)


@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def update_product(product_id: int, product_data: ProductCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE products SET nama_produk = ?, kategori = ?, harga = ? WHERE id = ?",
        (product_data.nama_produk, product_data.kategori, product_data.harga, product_id)
    )
    db.commit()
    
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Gagal update. Produk dengan ID {product_id} tidak ditemukan"
        )
        
    return {**product_data.model_dump(), "id": product_id}


@app.delete("/products/{product_id}", tags=["Products"])
def delete_product(product_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Gagal menghapus. Produk dengan ID {product_id} tidak ditemukan"
        )
        
    return {"message": f"Produk dengan ID {product_id} berhasil dihapus"}


# SOAL 2: REPORT - TOTAL BELANJA CUSTOMER

@app.get("/reports/customer-total", response_model=List[CustomerTotalReport], tags=["Reports"])
def get_customer_total(db: sqlite3.Connection = Depends(get_db)):
    """
    Menampilkan total belanja setiap customer diurutkan dari yang terbesar.
    Menggunakan JOIN dan fungsi agregasi SUM().
    """
    cursor = db.cursor()
    query = """
    SELECT c.nama, SUM(o.jumlah * p.harga) as total_belanja
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    JOIN products p ON o.product_id = p.id
    GROUP BY c.id, c.nama
    ORDER BY total_belanja DESC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


# SOAL 3: REPORT - CUSTOMER DI ATAS RATA-RATA BELANJA

@app.get("/reports/customer-above-average", response_model=List[CustomerAboveAverageReport], tags=["Reports"])
def get_customer_above_average(db: sqlite3.Connection = Depends(get_db)):
    """
    Menampilkan customer dengan total belanja di atas rata-rata belanja seluruh customer.
    Menggunakan JOIN, SUM(), dan Subquery.
    """
    cursor = db.cursor()
    query = """
    SELECT nama, total_belanja
    FROM (
        SELECT c.nama, SUM(o.jumlah * p.harga) as total_belanja
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        JOIN products p ON o.product_id = p.id
        GROUP BY c.id, c.nama
    ) AS customer_spending
    WHERE total_belanja > (
        SELECT AVG(total_spend_each)
        FROM (
            SELECT SUM(o2.jumlah * p2.harga) as total_spend_each
            FROM orders o2
            JOIN products p2 ON o2.product_id = p2.id
            GROUP BY o2.customer_id
        )
    );
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


# SOAL 4: REPORT - PRODUK TERLARIS PER KATEGORI

@app.get("/reports/top-product-by-category", response_model=List[TopProductReport], tags=["Reports"])
def get_top_product_by_category(db: sqlite3.Connection = Depends(get_db)):
    """
    Menampilkan produk terlaris (jumlah terjual terbanyak) per kategori.
    Menggunakan JOIN, SUM(), dan CTE dengan Window Function RANK().
    """
    cursor = db.cursor()
    query = """
    WITH product_sales AS (
        SELECT 
            p.kategori, 
            p.nama_produk, 
            SUM(o.jumlah) as total_terjual,
            RANK() OVER (PARTITION BY p.kategori ORDER BY SUM(o.jumlah) DESC) as rank_sales
        FROM products p
        JOIN orders o ON p.id = o.product_id
        GROUP BY p.id, p.kategori, p.nama_produk
    )
    SELECT kategori, nama_produk, total_terjual
    FROM product_sales
    WHERE rank_sales = 1;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


# SOAL 5: REPORT - KLASIFIKASI LEVEL CUSTOMER

@app.get("/reports/customer-level", response_model=List[CustomerLevelReport], tags=["Reports"])
def get_customer_level(db: sqlite3.Connection = Depends(get_db)):
    """
    Mengklasifikasikan level belanja customer menggunakan:
    - VIP (> 5.000.000)
    - Regular (1.000.000 s/d 5.000.000)
    - Basic (< 1.000.000)
    Menggunakan JOIN, SUM(), CTE, dan CASE statement.
    """
    cursor = db.cursor()
    query = """
    WITH customer_spending AS (
        SELECT c.nama, SUM(o.jumlah * p.harga) as total_belanja
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        JOIN products p ON o.product_id = p.id
        GROUP BY c.id, c.nama
    )
    SELECT 
        nama, 
        total_belanja,
        CASE 
            WHEN total_belanja > 5000000 THEN 'VIP'
            WHEN total_belanja BETWEEN 1000000 AND 5000000 THEN 'Regular'
            ELSE 'Basic'
        END as level_customer
    FROM customer_spending;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]