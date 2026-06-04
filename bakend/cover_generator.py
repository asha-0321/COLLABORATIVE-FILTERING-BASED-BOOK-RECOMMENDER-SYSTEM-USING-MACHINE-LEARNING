import pandas as pd
import requests
import os
import time

# Load dataset
df = pd.read_csv("books.csv")

# Folder to save covers
cover_folder = "static/book_covers"
os.makedirs(cover_folder, exist_ok=True)

# Default cover
default_cover = "static/images/default_book.png"

for index, row in df.iterrows():

    isbn = str(row['ISBN']).strip()
    title = str(row['Book-Title']).strip()

    file_path = f"{cover_folder}/{isbn}.jpg"

    # Skip if already exists
    if os.path.exists(file_path):
        continue

    try:
        # -------- GOOGLE BOOKS API --------
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = requests.get(google_url).json()

        if "items" in response:
            image_url = response["items"][0]["volumeInfo"]["imageLinks"]["thumbnail"]
            img = requests.get(image_url)

            with open(file_path, "wb") as f:
                f.write(img.content)

            print(f"Google cover saved: {title}")
            continue

    except:
        pass

    try:
        # -------- OPENLIBRARY FALLBACK --------
        openlib_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        img = requests.get(openlib_url)

        if img.status_code == 200 and len(img.content) > 1000:
            with open(file_path, "wb") as f:
                f.write(img.content)

            print(f"OpenLibrary cover saved: {title}")
            continue

    except:
        pass

    # -------- DEFAULT IMAGE --------
    if os.path.exists(default_cover):
        with open(default_cover, "rb") as src:
            with open(file_path, "wb") as dst:
                dst.write(src.read())

    print(f"Default cover used: {title}")

    # Avoid API rate limit
    time.sleep(0.1)

print("All covers processed successfully!")