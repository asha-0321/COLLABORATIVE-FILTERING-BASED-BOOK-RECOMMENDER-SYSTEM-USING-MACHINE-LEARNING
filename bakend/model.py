import numpy as np
import pandas as pd
import pickle

# -------------------------------
# Load Dataset (Fix dtype issue)
# -------------------------------
books = pd.read_csv('Books.csv', low_memory=False)
ratings = pd.read_csv('Ratings.csv', low_memory=False)
users = pd.read_csv('Users.csv', low_memory=False)

print("Datasets loaded")

# Convert Book-Rating to numeric (IMPORTANT FIX)
ratings['Book-Rating'] = pd.to_numeric(ratings['Book-Rating'], errors='coerce')

# Drop rows where rating is NaN
ratings.dropna(subset=['Book-Rating'], inplace=True)

# -------------------------------
# Clean Books Data
# -------------------------------
books = books[['ISBN','Book-Title','Book-Author','Image-URL-M']]

books.rename(columns={
    "Book-Title":"title",
    "Book-Author":"author",
    "Image-URL-M":"image"
}, inplace=True)

# Merge ratings + books
ratings_with_books = ratings.merge(books, on='ISBN')

print("Merged data")

# -------------------------------
# Popular Books DataFrame
# -------------------------------
num_rating_df = ratings_with_books.groupby('title')['Book-Rating'].count().reset_index()
num_rating_df.rename(columns={'Book-Rating':'num_ratings'}, inplace=True)

avg_rating_df = ratings_with_books.groupby('title')['Book-Rating'].mean().reset_index()
avg_rating_df.rename(columns={'Book-Rating':'avg_rating'}, inplace=True)

popular_df = num_rating_df.merge(avg_rating_df, on='title')
popular_df = popular_df.merge(books, on='title').drop_duplicates('title')

popular_df = popular_df.sort_values('num_ratings', ascending=False).head(50)

print("Popular DF created")

# -------------------------------
# Collaborative Filtering Model
# -------------------------------
x = ratings_with_books.groupby('User-ID')['Book-Rating'].count() > 200
educated_users = x[x].index

filtered_rating = ratings_with_books[ratings_with_books['User-ID'].isin(educated_users)]

y = filtered_rating.groupby('title')['Book-Rating'].count() >= 50
famous_books = y[y].index

final_ratings = filtered_rating[filtered_rating['title'].isin(famous_books)]

pt = final_ratings.pivot_table(index='title', columns='User-ID', values='Book-Rating')
pt.fillna(0, inplace=True)

print("Pivot table created")

# -------------------------------
# Save Pickle Files
# -------------------------------
pickle.dump(popular_df, open('popular.pkl','wb'))
pickle.dump(pt, open('pt.pkl','wb'))
pickle.dump(books, open('books.pkl','wb'))

print("Pickle files created successfully 🎉")
