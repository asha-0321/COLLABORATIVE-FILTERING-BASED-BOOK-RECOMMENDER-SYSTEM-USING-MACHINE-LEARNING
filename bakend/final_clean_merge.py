import pandas as pd

print("Loading datasets...")

telugu = pd.read_csv("datasets/telugu_books_fixed.csv")
tamil = pd.read_csv("datasets/tamil_books_fixed.csv")
hindi = pd.read_csv("datasets/hindi_books_fixed.csv")
kannada = pd.read_csv("datasets/kannada_books_fixed.csv")
malayalam = pd.read_csv("datasets/malayalam_books_fixed.csv")

print("Merging datasets...")

# Combine all
merged = pd.concat([telugu, tamil, hindi, kannada, malayalam], ignore_index=True)

# Remove duplicates (based on title)
merged.drop_duplicates(subset=["title"], inplace=True)

print("Saving final dataset...")

merged.to_csv("datasets/books_multilingual_final.csv", index=False)

print("✅ Dataset merged successfully!")