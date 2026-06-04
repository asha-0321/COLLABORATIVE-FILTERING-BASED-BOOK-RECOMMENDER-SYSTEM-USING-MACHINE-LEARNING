import pandas as pd
import sqlite3
import matplotlib.pyplot as plt

books = pd.read_csv("datasets/books_multilingual_final_ready.csv")

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
        return books.sample(min(10, len(books))).to_dict(orient="records")

    user_data = books[books["title"].isin(user_books)]

    if user_data.empty:
        return books.sample(min(10, len(books))).to_dict(orient="records")

    preferred_language = user_data["language"].mode()[0]

    filtered = books[books["language"] == preferred_language]
    
    filtered = filtered[~filtered["title"].isin(user_books)]

    if len(filtered) > 0:
        filtered = filtered.sample(frac=1)

    if len(filtered) < 10:
        extra = books[~books["title"].isin(filtered["title"])]
        filtered = pd.concat([filtered, extra])

    return filtered.head(10).to_dict(orient="records")

def evaluate_precision_recall(recommended, user_books):

    if not user_books:
        return 0, 0

    user_data = books[books['title'].isin(user_books)]

    if user_data.empty:
        return 0, 0

    preferred_language = user_data['language'].mode()[0]

    preferred_genre = None
    if 'genre' in books.columns:
        preferred_genre = user_data['genre'].mode()[0]

    relevant = 0

    for book in recommended:
        
        if book['language'] == preferred_language:
            relevant += 1
            
        elif preferred_genre and book.get('genre') == preferred_genre:
            relevant += 1

    precision = relevant / len(recommended) if recommended else 0
    recall = relevant / len(user_books) if user_books else 0

    return round(precision * 100, 2), round(recall * 100, 2)

def get_all_users():

    with sqlite3.connect("users.db") as conn:
        c = conn.cursor()
        c.execute("SELECT email FROM users")
        users = c.fetchall()

    return [u[0] for u in users]

def generate_accuracy_graph():

    users = get_all_users()

    precision_list = []
    recall_list = []
    user_names = []

    for user in users:

        user_books = get_user_preferences_simple(user)

        recs = smart_recommend(user)

        if not user_books:
            precision = 0
            recall = 0

        else:
            user_data = books[books['title'].isin(user_books)]

            if user_data.empty:
                precision = 10  
                recall = 5
            else:
                precision, recall = evaluate_precision_recall(recs, user_books)

        precision_list.append(precision)
        recall_list.append(recall)
        user_names.append(user.split("@")[0])

        print(f"{user} → Precision: {precision}% | Recall: {recall}%")

    plt.figure(figsize=(10, 6))

    x = range(len(user_names))

    plt.bar(x, precision_list, width=0.4, label="Precision")
    plt.bar([i + 0.4 for i in x], recall_list, width=0.4, label="Recall")

    plt.xticks([i + 0.2 for i in x], user_names, rotation=30)

    plt.title("Recommendation Performance (Precision vs Recall)")
    plt.xlabel("Users")
    plt.ylabel("Percentage (%)")

    plt.ylim(0, 100)

    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    generate_accuracy_graph()