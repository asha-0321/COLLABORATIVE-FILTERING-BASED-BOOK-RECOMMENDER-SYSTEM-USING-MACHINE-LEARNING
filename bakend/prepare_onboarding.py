import pandas as pd

# Load dataset
df = pd.read_csv("GoodReads_100k_books.csv")

# Clean nulls
df = df.dropna(subset=['author', 'genre'])

# -----------------------------
# Extract Top 20 Authors
# -----------------------------
top_authors = df['author'].value_counts().head(40)

print("Top 20 Authors:")
print(top_authors)

# -----------------------------
# Extract Top 15 Genres
# -----------------------------
# Genre column contains comma separated values
all_genres = []

for genres in df['genre']:
    for g in str(genres).split(','):
        all_genres.append(g.strip())

genre_series = pd.Series(all_genres)
top_genres = genre_series.value_counts().head(30)

print("\nTop 15 Genres:")
print(top_genres)