import pandas as pd

df = pd.read_excel(r"C:\Users\aymen\OneDrive\Bureau\Passage de grade\Enseignement.xlsx",
                   sheet_name="Module ", header=3)
df.columns = [str(c).strip() for c in df.columns]
df = df[df["Module"].notna()].copy()
df["Module"] = df["Module"].astype(str).str.strip()

print("=== Domaines distincts ===")
for d in df["Domaine du modules"].dropna().unique():
    print(" -", repr(d))

print("\n=== Module -> Lien (premier vu) ===")
seen = {}
for _, r in df.iterrows():
    m = r["Module"]
    l = r.get("Lien du module")
    if pd.notna(l) and m not in seen:
        seen[m] = str(l).strip()
for m in sorted(seen):
    print(f"  {m:<55} -> {seen[m]}")

n_with_link = len(seen)
n_modules = df["Module"].nunique()
print(f"\nModules avec lien: {n_with_link} / {n_modules}")

print("\n=== Modules SANS lien ===")
for m in sorted(set(df["Module"].unique()) - set(seen.keys())):
    print(" -", m)
