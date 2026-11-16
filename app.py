import os
from flask import Flask, render_template, request
import mysql.connector
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

def get_db():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'library_db')
    )

# F2.1 Search Books (WHERE) - WITH PREPARED STATEMENTS (BONUS)
@app.route('/')
@app.route('/search', methods=['GET', 'POST'])
def search_books():
    books = []
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch categories for dropdown
    cursor.execute("SELECT category_id, name FROM CATEGORY")
    categories = cursor.fetchall()
    
    if request.method == 'POST':
        title_kw = request.form.get('title', '')
        min_price = request.form.get('min_price', 0)
        max_price = request.form.get('max_price', 9999)
        category_id = request.form.get('category_id', '')

        # Prepared statement using %s placeholders (Bonus requirement)
        query = """
            SELECT b.book_id, b.title, b.price, b.publish_year, c.name AS category_name
            FROM BOOK b
            JOIN CATEGORY c ON b.category_id = c.category_id
            WHERE b.title LIKE %s 
              AND b.price BETWEEN %s AND %s
        """
        params = [f"%{title_kw}%", float(min_price), float(max_price)]

        if category_id:
            query += " AND b.category_id = %s"
            params.append(category_id)

        query += " ORDER BY b.price ASC"
        
        cursor.execute(query, tuple(params))
        books = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('search.html', books=books, categories=categories)

# F2.2 Catalogue (JOIN)
@app.route('/catalogue')
def catalogue():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.book_id, b.title, b.price, b.publish_year, 
               a.name AS author_name, p.name AS publisher_name, c.name AS category_name
        FROM BOOK b
        JOIN AUTHOR a ON b.author_id = a.author_id
        JOIN PUBLISHER p ON b.publisher_id = p.publisher_id
        JOIN CATEGORY c ON b.category_id = c.category_id
        ORDER BY b.book_id
    """)
    books = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('catalogue.html', books=books)

# F2.3 Reports (GROUP BY, HAVING)
@app.route('/reports')
def reports():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # (a) Category stats
    cursor.execute("""
        SELECT c.name AS category_name, COUNT(b.book_id) AS total_books, AVG(b.price) AS average_price
        FROM CATEGORY c
        LEFT JOIN BOOK b ON c.category_id = b.category_id
        GROUP BY c.category_id, c.name
    """)
    category_stats = cursor.fetchall()

    # (b) Authors with at least 2 books
    cursor.execute("""
        SELECT a.name AS author_name, COUNT(b.book_id) AS book_count
        FROM AUTHOR a
        JOIN BOOK b ON a.author_id = b.author_id
        GROUP BY a.author_id, a.name
        HAVING COUNT(b.book_id) >= 2
    """)
    top_authors = cursor.fetchall()

    # (c) Overall price totals
    cursor.execute("""
        SELECT SUM(price) AS total_price, MIN(price) AS min_price, MAX(price) AS max_price
        FROM BOOK
    """)
    library_stats = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('reports.html', category_stats=category_stats, top_authors=top_authors, library_stats=library_stats)

# F2.4 Loans (JOIN, LEFT JOIN)
@app.route('/loans')
def loans():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # (a) Unreturned loans
    cursor.execute("""
        SELECT l.loan_id, b.title AS book_title, m.name AS member_name, l.loan_date
        FROM LOAN l
        JOIN BOOK b ON l.book_id = b.book_id
        JOIN MEMBER m ON l.member_id = m.member_id
        WHERE l.return_date IS NULL
    """)
    active_loans = cursor.fetchall()

    # (b) Members who never borrowed
    cursor.execute("""
        SELECT m.member_id, m.name AS member_name, m.email
        FROM MEMBER m
        LEFT JOIN LOAN l ON m.member_id = l.member_id
        WHERE l.loan_id IS NULL
    """)
    no_loan_members = cursor.fetchall()

    # (c) Books never borrowed
    cursor.execute("""
        SELECT b.book_id, b.title
        FROM BOOK b
        LEFT JOIN LOAN l ON b.book_id = l.book_id
        WHERE l.loan_id IS NULL
    """)
    unborrowed_books = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('loans.html', active_loans=active_loans, no_loan_members=no_loan_members, unborrowed_books=unborrowed_books)

# F2.5 Most Borrowed (GROUP BY, ORDER BY, LIMIT)
@app.route('/analytics')
def analytics():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Top 3 books
    cursor.execute("""
        SELECT b.title, COUNT(l.loan_id) AS total_loans
        FROM BOOK b
        JOIN LOAN l ON b.book_id = l.book_id
        GROUP BY b.book_id, b.title
        ORDER BY total_loans DESC
        LIMIT 3
    """)
    top_books = cursor.fetchall()

    # Member with most loans
    cursor.execute("""
        SELECT m.name AS member_name, COUNT(l.loan_id) AS total_loans
        FROM MEMBER m
        JOIN LOAN l ON m.member_id = l.member_id
        GROUP BY m.member_id, m.name
        ORDER BY total_loans DESC
        LIMIT 1
    """)
    top_member = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('analytics.html', top_books=top_books, top_member=top_member)

# F2.6 Authors and Books (LEFT JOIN, JOIN)
@app.route('/authors')
def authors():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # (a) Authors book counts (including 0)
    cursor.execute("""
        SELECT a.name AS author_name, COUNT(b.book_id) AS book_count
        FROM AUTHOR a
        LEFT JOIN BOOK b ON a.author_id = b.author_id
        GROUP BY a.author_id, a.name
    """)
    authors_book_count = cursor.fetchall()

    # (b) Same country author and publisher
    cursor.execute("""
        SELECT b.title, a.name AS author_name, p.name AS publisher_name, a.country
        FROM BOOK b
        JOIN AUTHOR a ON b.author_id = a.author_id
        JOIN PUBLISHER p ON b.publisher_id = p.publisher_id
        WHERE a.country = p.country
    """)
    same_country_books = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('authors.html', authors_book_count=authors_book_count, same_country_books=same_country_books)

if __name__ == '__main__':
    app.run(debug=True)