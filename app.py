from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_from_directory 
import requests
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from flask import jsonify
from nlp_summary import multilingual_summary
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
app.secret_key = "bloomverse_secret_key"

serializer = URLSafeTimedSerializer(app.secret_key)


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'chikkalabhagyalakshmi65@gmail.com'
app.config['MAIL_PASSWORD'] = 'eueuhqukbyknjdgo'

mail = Mail(app)

UPLOAD_FOLDER = "static/profile_images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT UNIQUE,
                phone TEXT,
                password TEXT,
                profile_image TEXT,
                role TEXT DEFAULT 'user'
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                book_title TEXT,
                author TEXT,
                image TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT UNIQUE,
                favorite_author TEXT,
                favorite_genre TEXT,
                favorite_language text
            )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        query TEXT,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
        c.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    book_title TEXT,
    rating INTEGER,
    review TEXT,
    likes INTEGER DEFAULT 0
)
""")
        c.execute("""
CREATE TABLE IF NOT EXISTS recently_viewed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    book_title TEXT,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
        conn.commit()

init_db()

import os
import re

books = pd.read_csv("datasets/books_multilingual_final_ready.csv")
books = books.dropna(subset=["title", "author"])

COVER_FOLDER = "static/book_covers"

def get_cover(row):

    
    if "img" in row and isinstance(row["img"], str) and row["img"].startswith("http"):
        return row["img"]

    if "image" in row and isinstance(row["image"], str) and row["image"].startswith("http"):
        return row["image"]


    title = row["title"]

    clean = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')

    possible = [
        f"{clean}.jpg",
        f"{clean}_telugu.jpg",
        f"{clean}_tamil.jpg",
        f"{clean}_hindi.jpg",
        f"{clean}_kannada.jpg",
        f"{clean}_malayalam.jpg"
    ]

    for file in possible:
        full = os.path.join(COVER_FOLDER, file)
        if os.path.exists(full):
            return f"book_covers/{file}"


    return "book_covers/default.jpg"

books["img"] = books.apply(get_cover, axis=1)

IMG_COLUMN = "img"

avoid_genres = [
    "Romance",
    "Paranormal",
    "Erotica",
    "Young Adult Romance"
]

def filter_academic_books(df):
    if 'genre' in df.columns:
        return df[~df['genre'].str.contains('|'.join(avoid_genres),
                                            case=False,
                                            na=False)]
    return df

def get_google_books_data(title, author=None):
    try:
        url = "https://www.googleapis.com/books/v1/volumes"

        query = title
        if author:
            query += f"+inauthor:{author}"

        params = {
            "q": query,
            "maxResults": 1
        }

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if "items" in data and len(data["items"]) > 0:
            volume = data["items"][0]["volumeInfo"]

            return {
                "preview": volume.get("previewLink"),
                "description": volume.get("description")
            }

    except Exception as e:
        print("Google API Error:", e)

    return {}


def get_amazon_link(title):
    return f"https://www.amazon.in/s?k={title.replace(' ', '+')}"


def get_openlibrary_link(title):
    return f"https://openlibrary.org/search?q={title.replace(' ', '+')}"

def get_recommendations(user_email):
    with sqlite3.connect("users.db") as conn:
        df = pd.read_sql_query(
            "SELECT user_email, book_title, rating FROM reviews",
            conn
        )

    
    if df.empty:
        sample = filter_academic_books(books)
        return sample.sample(10).to_dict(orient="records")
    # Create pivot table
    pivot = df.pivot_table(
        index='user_email',
        columns='book_title',
        values='rating'
    ).fillna(0)


    if pivot.shape[0] < 2:
        sample = filter_academic_books(books)
        return sample.sample(10).to_dict(orient="records")
    
    similarity = cosine_similarity(pivot)

    sim_df = pd.DataFrame(
        similarity,
        index=pivot.index,
        columns=pivot.index
    )

    
    if user_email not in sim_df.index:
        sample = filter_academic_books(books)
        return sample.sample(10).to_dict(orient="records")

    similar_users = sim_df[user_email].sort_values(ascending=False)[1:4].index

    recommended_books = df[df.user_email.isin(similar_users)]
    recommended_titles = recommended_books.book_title.unique()

    result = books[books.title.isin(recommended_titles)]

    
    if result.empty:
        safe_books = filter_academic_books(books)
        return safe_books.sort_values(by="rating", ascending=False).head(10).to_dict(orient="records")
    result = filter_academic_books(result)
    return result.head(10).to_dict(orient="records")

def because_you_read(user_email):

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("""
            SELECT book_title
            FROM recently_viewed
            WHERE user_email=?
            ORDER BY viewed_at DESC
            LIMIT 1
        """, (user_email,))

        last_book = c.fetchone()

    if not last_book:
        return []

    title = last_book[0]

    book_row = books[books["title"] == title]

    if book_row.empty:
        return []

    genre = book_row.iloc[0]["genre"]
    language = book_row.iloc[0]["language"]

    recs = books[
        (books["genre"] == genre) &
        (books["language"] == language) &
        (books["title"] != title)
    ]

    recs = filter_academic_books(recs)

    return recs.sort_values("popularity_score", ascending=False)\
            .head(10)\
            .to_dict(orient="records")
            
def get_user_preferences_simple(user_email):

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("""
            SELECT book_title FROM recently_viewed
            WHERE user_email=?
        """, (user_email,))

        data = c.fetchall()

    return [d[0] for d in data]


def smart_recommend(user_email):

    user_books = get_user_preferences_simple(user_email)

    if not user_books:
        return books.sample(10).to_dict(orient="records")

    user_data = books[books["title"].isin(user_books)]

    if user_data.empty:
        return books.sample(10).to_dict(orient="records")

    preferred_language = user_data["language"].mode()[0]

    filtered = books[books["language"] == preferred_language]

    if "rating" in filtered.columns:
        filtered = filtered.sort_values(by="rating", ascending=False)

    filtered = filtered[~filtered["title"].isin(user_books)]

    return filtered.head(10).to_dict(orient="records")
    
    
@app.context_processor
def inject_user():
    return dict(current_user=session.get("user"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            with sqlite3.connect("users.db") as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO users (username, email, phone, password)
                    VALUES (?, ?, ?, ?)
                """, (username, email, phone, hashed_password))
                conn.commit()
        except sqlite3.IntegrityError:
            flash("Email already exists!")
            return redirect(url_for("register"))

        session["user"] = username
        session["email"] = email

        try:
            msg = Message(
                subject="Welcome to BloomVerse 📚",
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )

            msg.html = f"""
            <h2>Welcome to BloomVerse 📚</h2>
            <p>Hi <b>{username}</b>,</p>
            <p>You have successfully registered to <b>BloomVerse</b>.</p>
            <p>Start exploring books and enjoy your journey 📚✨</p>
            <p>Happy Reading! ✨</p>
            """

            mail.send(msg)

        except Exception as e:
            print("Email not sent:", e)  # optional (for debugging)

        return redirect(url_for("explore"))

    return render_template("register.html")

@app.route("/download/<filename>")
def download_book(filename):
    return send_from_directory(
        "static/books",
        filename,
        as_attachment=True
    )

@app.route("/read/<filename>")
def read_book(filename):
    return render_template("reader.html", filename=filename)

@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            user = c.fetchone()

        if user and check_password_hash(user[4], password):
            session["user"] = user[1]
            session["email"] = user[2]
            return redirect(url_for("explore"))
        else:
            flash("Invalid credentials!")

    return render_template("user_login.html")

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND role='admin'", (email,))
            admin = c.fetchone()

        if admin and check_password_hash(admin[4], password):
            session["admin"] = admin[1]
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials!")

    return render_template("admin_login.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM reviews")
        total_reviews = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM wishlist")
        total_wishlist = c.fetchone()[0]

    return render_template("admin_dashboard.html",
                        total_users=total_users,
                        total_reviews=total_reviews,
                        total_wishlist=total_wishlist)
    
@app.route("/admin_users")
def admin_users():
    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, email FROM users")
        users = c.fetchall()

    return render_template("admin_users.html", users=users)

@app.route("/user_details/<email>")
def user_details(email):
    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        
        c.execute("SELECT book_title, rating FROM reviews WHERE user_email=?", (email,))
        reviews = c.fetchall()
        
        c.execute("SELECT book_title FROM wishlist WHERE username=(SELECT username FROM users WHERE email=?)", (email,))
        wishlist = c.fetchall()

    return render_template("user_details.html", reviews=reviews, wishlist=wishlist, email=email)

@app.route("/admin_reviews")
def admin_reviews():
    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT user_email, book_title, rating FROM reviews")
        reviews = c.fetchall()

    return render_template("admin_reviews.html", reviews=reviews)

@app.route("/admin_wishlist")
def admin_wishlist():
    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT username, book_title FROM wishlist")
        wishlist = c.fetchall()

    return render_template("admin_wishlist.html", wishlist=wishlist)

@app.route("/delete_user/<email>")
def delete_user(email):

    if email == "admin@gmail.com":
        return "Cannot delete admin!"

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("SELECT username FROM users WHERE email=?", (email,))
        user = c.fetchone()

        if user:
            username = user[0]

            c.execute("DELETE FROM users WHERE email=?", (email,))

            c.execute("DELETE FROM reviews WHERE user_email=?", (email,))
            c.execute("DELETE FROM wishlist WHERE username=?", (username,))
            c.execute("DELETE FROM search_history WHERE user_email=?", (email,))
            c.execute("DELETE FROM recently_viewed WHERE user_email=?", (email,))

        conn.commit()

    return redirect(url_for("admin_users"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            user = c.fetchone()

        if user:
            token = serializer.dumps(email, salt="password-reset")

            reset_link = url_for("reset_password", token=token, _external=True)

            try:
                msg = Message(
                    subject="Password Reset - BloomVerse",
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[email]
                )

                msg.html = f"""
                <h3>Password Reset Request</h3>
                <p>Click below link to reset your password:</p>
                <a href="{reset_link}">{reset_link}</a>
                <p>This link will expire in 10 minutes.</p>
                """

                mail.send(msg)

                flash("Reset link sent to your email!")
            except Exception as e:
                print(e)
                flash("Error sending email")

        else:
            flash("Email not found!")

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset", max_age=600)
    except:
        return "Invalid or expired link"

    if request.method == "POST":
        new_password = request.form.get("password")
        hashed_password = generate_password_hash(new_password)

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET password=? WHERE email=?",
                    (hashed_password, email))
            conn.commit()

        flash("Password updated successfully!")
        return redirect(url_for("user_login"))

    return render_template("reset_password.html")
def evaluate_recommendation(books, smart_books, user_books):
    if not user_books:
        return 0

    # Extract titles from smart recommendations
    smart_titles = [book["title"] for book in smart_books]

    # Find matching books
    match_count = len(set(smart_titles) & set(user_books))

    accuracy = match_count / len(user_books)

    return round(accuracy, 2)


@app.route("/explore")
def explore():
    if "user" not in session:
        return redirect(url_for("user_login"))

    user_email = session["email"]

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT favorite_author, favorite_genre
            FROM user_preferences
            WHERE user_email=?
        """, (user_email,))
        prefs = c.fetchone()

    recommended = books.copy()

    if prefs and len(prefs) > 2 and prefs[2]:
        fav_languages = prefs[2].split(",")
        recommended = recommended[recommended["language"].isin(fav_languages)]

    if recommended.empty:
        recommended = books.sample(20)

    clean_books = books

    if IMG_COLUMN:
        clean_books = books[
            books[IMG_COLUMN].notna() & (books[IMG_COLUMN] != "")
        ]

    if "rating" in clean_books.columns:
        top_rated = clean_books.sort_values(by="rating", ascending=False).head(30)
    else:
        top_rated = clean_books.sample(20)

    if "totalratings" in clean_books.columns:
        trending = clean_books.sort_values(by="totalratings", ascending=False).head(30)
    else:
        trending = clean_books.sample(20)

    ai_recommended = get_recommendations(session["email"])
    because_read = because_you_read(session["email"])
    smart_books = smart_recommend(session["email"])
    
    user_books = get_user_preferences_simple(session["email"])
    accuracy = evaluate_recommendation(books, smart_books, user_books)

    print("Recommendation Accuracy:", accuracy)

    recommended = filter_academic_books(recommended)
    top_rated = filter_academic_books(top_rated)
    trending = filter_academic_books(trending)

    ai_recommended_df = pd.DataFrame(ai_recommended)
    ai_recommended_df = filter_academic_books(ai_recommended_df)

    if IMG_COLUMN:
        recommended[IMG_COLUMN] = recommended[IMG_COLUMN].astype(str)
        top_rated[IMG_COLUMN] = top_rated[IMG_COLUMN].astype(str)
        trending[IMG_COLUMN] = trending[IMG_COLUMN].astype(str)

        if not ai_recommended_df.empty and IMG_COLUMN in ai_recommended_df.columns:
            ai_recommended_df[IMG_COLUMN] = ai_recommended_df[IMG_COLUMN].astype(str)

    return render_template(
        "explore.html",
        recommended=recommended.head(12).to_dict(orient="records"),
        top_rated=top_rated.to_dict(orient="records"),
        trending=trending.to_dict(orient="records"),
        ai_recommended=ai_recommended_df.to_dict(orient="records"),
        because_read=because_read,
        smart_books=smart_books
    )
    
@app.route("/search")
def search():
    if "user" not in session:
        return redirect(url_for("user_login"))

    query = request.args.get("query")

    if not query:
        return redirect(url_for("explore"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("""
            DELETE FROM search_history
            WHERE user_email=? AND query=?
        """,(session["email"], query))

        c.execute("""
            INSERT INTO search_history (user_email, query)
            VALUES (?, ?)
        """, (session["email"], query))
        conn.commit()

    results = books[
        books["title"].str.contains(query, case=False, na=False)
    ]

    results = filter_academic_books(results)

    return render_template(
        "explore.html",
        recommended=results.head(20).to_dict(orient="records"),
        top_rated=[],
        trending=[],
        is_search=True,
        search_query=query
    )
    
@app.route("/history")
def history():
    if "user" not in session:
        return {"results": []}

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT query
            FROM search_history
            WHERE user_email=?
            ORDER BY searched_at DESC
            LIMIT 5
        """, (session["email"],))
        rows = c.fetchall()

    return {"results": [row[0] for row in rows]}
@app.route("/suggest")
def suggest():
    query = request.args.get("q", "")

    if not query:
        return {"results": []}

    results = books[
        books["title"].str.contains(query, case=False, na=False)
    ].head(5)

    suggestions = []

    for _, book in results.iterrows():
        suggestions.append({
            "title": book["title"],
            "author": book["author"]
        })

    return {"results": suggestions}

@app.route("/book/<title>")
def book_detail(title):

    if "user" not in session:
        return redirect(url_for("user_login"))

    book = books[books["title"] == title]

    if book.empty:
        return "Book not found"

    book_data = book.iloc[0]

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO recently_viewed (user_email, book_title)
            VALUES (?, ?)
        """, (session["email"], title))
        conn.commit()

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT user_email, rating, review, likes
            FROM reviews
            WHERE book_title=?
        """, (title,))
        reviews = c.fetchall()

    amazon_link = get_amazon_link(title)

    if not amazon_link:
        amazon_link = f"https://www.flipkart.com/search?q={title.replace(' ','+')}"

    openlibrary_link = get_openlibrary_link(title)


    google_data = get_google_books_data(title, book_data["author"])

    preview = google_data.get("preview") if google_data else None
    description = google_data.get("description") if google_data else None

    google_books_link = f"https://www.google.com/search?q={title.replace(' ', '+')}+google+books"
    free_pdf_link = f"https://www.google.com/search?q={title.replace(' ', '+')}+pdf"
    gutenberg_link = f"https://www.gutenberg.org/ebooks/search/?query={title.replace(' ', '+')}"

    return render_template(
        "book_detail.html",
        book=book_data,
        img_column=IMG_COLUMN,
        preview=preview,
        description=description,
        amazon_link=amazon_link,
        openlibrary_link=openlibrary_link,
        gutenberg_link=gutenberg_link,
        google_books_link=google_books_link,
        free_pdf_link=free_pdf_link,
        reviews=reviews
    )
    
@app.route("/review/<title>")
def review_page(title):
    if "user" not in session:
        return redirect(url_for("user_login"))

    book = books[books["title"] == title]

    if book.empty:
        return "Book not found"

    book_data = book.iloc[0]

    return render_template(
        "review_page.html",
        book=book_data,
        img_column=IMG_COLUMN
    )
    
@app.route("/add_to_wishlist", methods=["POST"])
def add_to_wishlist():
    if "user" not in session:
        return redirect(url_for("user_login"))

    title = request.form.get("book_title")
    author = request.form.get("author")
    image = request.form.get("image")

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO wishlist (username, book_title, author, image)
            VALUES (?, ?, ?, ?)
        """, (session["user"], title, author, image))
        conn.commit()

    return redirect(url_for("explore"))

@app.route("/add_review", methods=["POST"])
def add_review():
    if "user" not in session:
        return redirect(url_for("user_login"))

    rating = request.form.get("rating")
    review = request.form.get("review")
    book = request.form.get("book_title")

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO reviews (user_email, book_title, rating, review)
            VALUES (?, ?, ?, ?)
        """, (session["email"], book, rating, review))
        conn.commit()

    return redirect(url_for("book_detail", title=book))

@app.route("/wishlist")
def wishlist():
    if "user" not in session:
        return redirect(url_for("user_login"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT book_title, author, image
            FROM wishlist
            WHERE username=?
        """, (session["user"],))
        books_data = c.fetchall()

    return render_template("wishlist.html", books=books_data)

@app.route("/remove_from_wishlist", methods=["POST"])
def remove_from_wishlist():
    if "user" not in session:
        return redirect(url_for("user_login"))

    title = request.form.get("book_title")

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            DELETE FROM wishlist
            WHERE username=? AND book_title=?
        """, (session["user"], title))
        conn.commit()

    return redirect(url_for("wishlist"))

@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("user_login"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("""
            SELECT username, email, phone, profile_image
            FROM users
            WHERE email=?
        """, (session["email"],))
        user = c.fetchone()

        c.execute("""
            SELECT COUNT(*)
            FROM wishlist
            WHERE username=?
        """, (session["user"],))
        wishlist_count = c.fetchone()[0]

        c.execute("""
            SELECT book_title, rating, review
            FROM reviews
            WHERE user_email=?
            ORDER BY id DESC
        """, (session["email"],))
        user_reviews = c.fetchall()

    return render_template(
        "profile.html",
        user=user,
        wishlist_count=wishlist_count,
        user_reviews=user_reviews
    )
    
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect(url_for("user_login"))

    if request.method == "POST":
        username = request.form.get("username")
        phone = request.form.get("phone")

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users
                SET username=?, phone=?
                WHERE email=?
            """, (username, phone, session["email"]))
            conn.commit()

        session["user"] = username
        flash("Profile updated successfully!")
        return redirect(url_for("profile"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT username, email, phone
            FROM users
            WHERE email=?
        """, (session["email"],))
        user = c.fetchone()

    return render_template("edit_profile.html", user=user) 

@app.route("/upload_profile_image", methods=["POST"])
def upload_profile_image():
    if "user" not in session:
        return redirect(url_for("user_login"))

    file = request.files.get("profile_image")

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users SET profile_image=?
                WHERE email=?
            """, (filename, session["email"]))
            conn.commit()

    return redirect(url_for("profile"))

@app.route("/remove_profile_image", methods=["POST"])
def remove_profile_image():
    if "user" not in session:
        return redirect(url_for("user_login"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE users SET profile_image=NULL
            WHERE email=?
        """, (session["email"],))
        conn.commit()

    return redirect(url_for("profile"))

@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user" not in session:
        return redirect(url_for("user_login"))

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()

        c.execute("DELETE FROM wishlist WHERE username=?", (session["user"],))

        c.execute("DELETE FROM user_preferences WHERE user_email=?", (session["email"],))

        c.execute("DELETE FROM users WHERE email=?", (session["email"],))

        conn.commit()

    session.clear()
    return redirect(url_for("index"))

@app.route("/change_password", methods=["POST"])
def change_password():
    if "user" not in session:
        return redirect(url_for("user_login"))

    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE email=?", (session["email"],))
        user = c.fetchone()

        if user and check_password_hash(user[0], current_password):
            hashed = generate_password_hash(new_password)
            c.execute("UPDATE users SET password=? WHERE email=?",
                    (hashed, session["email"]))
            conn.commit()
            flash("Password updated successfully!")
        else:
            flash("Current password incorrect!")

    return redirect(url_for("profile"))

@app.route("/upload_cover_image", methods=["POST"])
def upload_cover_image():
    if "user" not in session:
        return redirect(url_for("user_login"))

    file = request.files.get("cover_image")

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        with sqlite3.connect("users.db") as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users SET cover_image=?
                WHERE email=?
            """, (filename, session["email"]))
            conn.commit()

    return redirect(url_for("profile"))

@app.route("/preferences")
def preferences():

    languages = sorted(books["language"].dropna().unique())

    return render_template(
        "select_language.html",
        languages=languages
    )
    
@app.route("/authors/<language>")
def language_authors(language):

    lang_books = books[books["language"] == language]

    ignore_authors = ["Traditional", "Various", "Anonymous"]

    authors = sorted(
        lang_books[
        ~lang_books["author"].isin(ignore_authors)
    ]["author"].dropna().unique()
)
    return render_template(
        "authors_by_language.html",
        language=language,
        authors=authors
    )
    
@app.route("/books/<author>")
def author_books(author):

    author_books = books[books["author"] == author]

    return render_template(
        "author_books.html",
        author=author,
        books=author_books.to_dict(orient="records")
    )
  
@app.route("/generate_summary", methods=["POST"])
def generate_summary():

    title = request.form.get("title")

    book = books[books["title"] == title]

    if book.empty:
        return {"summary": "Book not found"}

    author = book.iloc[0]["author"]
    genre = book.iloc[0].get("genre", "literature")
    language = book.iloc[0].get("language", "English")

    description = book.iloc[0].get("description", "")

    if not description or len(description) < 100:

        if language == "Telugu":
            description = f"""
            {title} ఒక ప్రసిద్ధ {genre} పుస్తకం, దీనిని {author} రచించారు.
            ఈ పుస్తకం జీవితం, నీతి, మనుషుల ప్రవర్తన మరియు సామాజిక విలువలను వివరిస్తుంది.
            ఇందులో ఉన్న పద్యాలు మరియు భావాలు పాఠకులకు ఆలోచన కలిగిస్తాయి.
            ఈ పుస్తకం తెలుగు సాహిత్యంలో ఒక ముఖ్యమైన స్థానం కలిగి ఉంది.
            """

        elif language == "Hindi":
            description = f"""
            {title} एक प्रसिद्ध {genre} पुस्तक है जिसे {author} ने लिखा है।
            यह पुस्तक मानव जीवन, नैतिकता और सामाजिक मूल्यों पर आधारित है।
            इसमें दिए गए विचार पाठकों को प्रेरित करते हैं।
            यह हिंदी साहित्य में एक महत्वपूर्ण कृति मानी जाती है।
            """

        elif language == "Tamil":
            description = f"""
            {title} ஒரு முக்கியமான {genre} புத்தகம், இதை {author} எழுதியுள்ளார்.
            இந்த புத்தகம் மனித வாழ்க்கை, உணர்ச்சிகள் மற்றும் சமூக மதிப்புகளை விளக்குகிறது.
            இது வாசகர்களுக்கு சிந்தனை தூண்டும் ஒரு சிறந்த படைப்பு.
            """

        elif language == "Kannada":
            description = f"""
            {title} ಒಂದು ಪ್ರಮುಖ {genre} ಪುಸ್ತಕ, ಇದನ್ನು {author} ರಚಿಸಿದ್ದಾರೆ.
            ಈ ಪುಸ್ತಕ ಮಾನವ ಜೀವನ, ಭಾವನೆಗಳು ಮತ್ತು ಸಾಮಾಜಿಕ ಮೌಲ್ಯಗಳನ್ನು ವಿವರಿಸುತ್ತದೆ.
            ಇದು ಓದುಗರಿಗೆ ಪ್ರೇರಣೆ ನೀಡುವ ಉತ್ತಮ ಕೃತಿ.
            """

        elif language == "Malayalam":
            description = f"""
            {title} ഒരു പ്രധാന {genre} പുസ്തകമാണ്, ഇത് {author} എഴുതിയത്.
            ഈ പുസ്തകം മനുഷ്യജീവിതം, വികാരങ്ങൾ, സാമൂഹിക മൂല്യങ്ങൾ എന്നിവയെ കുറിച്ച് പറയുന്നു.
            ഇത് വായനക്കാരെ ചിന്തിപ്പിക്കുന്ന ഒരു മികച്ച കൃതിയാണ്.
            """

        else:
            description = f"""
            {title} is a well-known {genre} book written by {author}.
            It explores themes like human life, emotions, and moral values.
            The book provides meaningful insights and engaging storytelling.
            It is considered an important work in literature.
            """
    summary = multilingual_summary(description, language)

    return {"summary": summary}
if __name__ == "__main__":
    app.run(debug=True)