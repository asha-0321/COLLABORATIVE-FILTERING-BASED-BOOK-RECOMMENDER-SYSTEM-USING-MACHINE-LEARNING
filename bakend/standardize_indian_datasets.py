import pandas as pd

# Files and their language values
files_with_language = {
    "GoodReads_100k_books_updated.csv": "English",
    "hindi_books_fixed.csv": "Hindi",
    "kannada_books_fixed.csv": "Kannada",
    "malayalam_books_fixed.csv": "Malayalam",
    "tamil_books_fixed.csv": "Tamil",
    "telugu_books_fixed.csv": "Telugu"
}

# Process each dataset
for filename, lang in files_with_language.items():
    print(f"\nProcessing {filename}...")

    df = pd.read_csv(f"datasets/{filename}")

    # Add or overwrite language column
    df["language"] = lang

    # Save back
    df.to_csv(f"datasets/{filename}", index=False)

    print(f"✅ language column set to {lang}")

# Now handle books_multilingual.csv separately
print("\nProcessing books_multilingual.csv...")

df_multi = pd.read_csv("datasets/books_multilingual.csv")

if "language" not in df_multi.columns:
    print("⚠ language column not found in books_multilingual.csv")
else:
    print("✅ language column already exists in books_multilingual.csv")

print("\n🎉 All language columns handled successfully!")